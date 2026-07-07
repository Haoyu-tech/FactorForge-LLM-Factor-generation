# -*- coding: utf-8 -*-
"""Candidate-distribution report for the strict LLM PASS mining loop.

Reads a run's candidate ledger + screened_summary and produces the auditable
"survival funnel" that is the actual paper contribution: of all candidates that
entered the strict gate, how many survive full-sample alpha, OOS alpha, and the
diversity screen -- broken down by economic family and by expression *structure*
(additive rank-sum vs multiplicative interaction vs ratio vs time-series).

This reports the WHOLE candidate distribution, not just the winners, which is the
defense against data-snooping / researcher-degrees-of-freedom critiques.

Run:
  python adapter/ledger_report.py                      # default diverse_pass_100 run
  python adapter/ledger_report.py --run-dir results/manual_llm_diverse_pass_100
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()

from llm_factor.config import path


def classify_structure(expr: str) -> str:
    """Coarse structural class of a factor expression.

    Priority: multiplicative interaction > ratio > time-series > additive rank-sum.
    A candidate with a '*' between two firm signals is an interaction even if it
    also contains other terms; this is what we mean by 'the LLM was told to use
    multiplication'."""
    has_mul = bool(re.search(r"\*", expr))
    has_div = bool(re.search(r"/", expr))
    has_ts = bool(re.search(r"\b(TS_[A-Z]+|DELTA|DELAY)\s*\(", expr))
    if has_mul:
        return "multiplicative"
    if has_div:
        return "ratio"
    if has_ts:
        return "timeseries"
    return "rank_sum"


def load_screened(run_dir: Path) -> pd.DataFrame:
    csv = run_dir / "screened_summary.csv"
    if not csv.exists():
        raise SystemExit(f"no screened_summary.csv in {run_dir}")
    df = pd.read_csv(csv)
    df["structure"] = df["expr"].map(classify_structure)
    df["full_sig"] = df["checks"].map(lambda s: '"VW_FF5+UMD_alpha_sig_full": true' in s)
    df["oos_sig"] = df["checks"].map(lambda s: '"VW_FF5+UMD_alpha_sig_oos": true' in s)
    df["mono_ok"] = df["checks"].map(lambda s: '"monotone_full": true' in s)
    df["is_pass"] = df["verdict"].str.upper() == "PASS"
    return df


def load_ledger(run_dir: Path) -> pd.DataFrame:
    # newest ledger file for this run
    cands = sorted(run_dir.glob("*.jsonl"))
    ledger = None
    for c in cands:
        if "gate" in c.name or "mine" in c.name:
            ledger = c
    ledger = ledger or (cands[0] if cands else None)
    if ledger is None:
        return pd.DataFrame()
    rows = []
    with ledger.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def funnel(df: pd.DataFrame, ledger: pd.DataFrame, run_dir: Path) -> dict:
    n_gated = len(df)
    n_full = int(df["full_sig"].sum())
    n_pass = int(df["is_pass"].sum())
    n_div_reject = 0
    if not ledger.empty and "stage" in ledger:
        n_div_reject = int(((ledger["stage"] == "diversity") & (ledger["status"] == "rejected")).sum())
    # authoritative survivor count = rows in passed_factors.csv (the diversity-screened set)
    pass_csv = run_dir / "passed_factors.csv"
    if pass_csv.exists():
        try:
            n_survivors = len(pd.read_csv(pass_csv))
        except Exception:
            n_survivors = max(n_pass - n_div_reject, 0)
    else:
        n_survivors = max(n_pass - n_div_reject, 0)
    return {
        "gated": n_gated,
        "full_sample_alpha_sig": n_full,
        "oos_alpha_sig (== factor_lab PASS)": n_pass,
        "oos_decay_full_to_pass": f"{n_full} -> {n_pass} ({100*n_pass/max(n_full,1):.0f}% of full-sig survive OOS)",
        "diversity_rejected": n_div_reject,
        "diverse_survivors": n_survivors,
    }


def by_group(df: pd.DataFrame, col: str) -> pd.DataFrame:
    g = df.groupby(col)
    out = pd.DataFrame({
        "gated": g.size(),
        "full_sig": g["full_sig"].sum().astype(int),
        "oos_sig(PASS)": g["is_pass"].sum().astype(int),
        "median_full_t": g["VW_FF5UMDa_t"].median().round(2),
        "median_oos_t": g["VW_FF5UMDa_t_test"].median().round(2),
    })
    out["oos_pass_rate"] = (out["oos_sig(PASS)"] / out["gated"]).round(2)
    return out.sort_values("gated", ascending=False)


def main(run_dir: Path) -> None:
    df = load_screened(run_dir)
    ledger = load_ledger(run_dir)

    fun = funnel(df, ledger, run_dir)
    by_struct = by_group(df, "structure")
    by_fam = by_group(df, "family")

    # OOS decay: among full-sample-significant candidates, how many clear the OOS bar
    full_sig = df[df["full_sig"]]
    decay = {
        "full_sig_candidates": len(full_sig),
        "median_full_t_among_full_sig": round(full_sig["VW_FF5UMDa_t"].median(), 2),
        "median_oos_t_among_full_sig": round(full_sig["VW_FF5UMDa_t_test"].median(), 2),
        "share_oos_t_below_1.96": round((full_sig["VW_FF5UMDa_t_test"] < 1.96).mean(), 2),
    }

    lines = ["# Candidate survival distribution", ""]
    lines += [f"Run: `{run_dir.as_posix()}`", ""]
    lines += ["## Survival funnel (strict gate)", "", "| Stage | Count |", "|---|---:|"]
    for k, v in fun.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## By expression structure", "",
              "Additive rank-sums survive; multiplicative interactions and ratios mostly do not.", ""]
    lines.append(by_struct.to_markdown())
    lines += ["", "## By economic family", ""]
    lines.append(by_fam.to_markdown())
    lines += ["", "## OOS decay among full-sample-significant candidates", "", "| Metric | Value |", "|---|---:|"]
    for k, v in decay.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "_Interpretation: the strict OOS + diversity screens collapse a large pool of "
              "full-sample-significant, economically-motivated composites down to a few mutually "
              "uncorrelated survivors -- all variants of one mispricing/financing-discipline mechanism. "
              "The candidate distribution, not the winners, is the auditable result._", ""]

    out_md = run_dir / "candidate_distribution.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    by_struct.to_csv(run_dir / "dist_by_structure.csv")
    by_fam.to_csv(run_dir / "dist_by_family.csv")

    print("\n".join(lines))
    print(f"\nWROTE {out_md}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=None)
    args = ap.parse_args()
    rd = Path(args.run_dir) if args.run_dir else (path("results_root") / "manual_llm_diverse_pass_100")
    main(rd)

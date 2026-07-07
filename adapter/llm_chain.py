# -*- coding: utf-8 -*-
"""Run the FULL evaluation chain on LLM-generated candidates.

Chain (all on the same panel, VW, Newey-West):
  1_factor_lab      strict gate: EW/VW FF5+UMD alpha full+OOS, decile monotonicity -> PASS/FAIL
  reports/          per-factor bundle: chart + json + derivation tree + formula tree
  2_spanning        increment vs own components AND the canonical Kelly anomaly zoo
  3_walk_forward    expanding-window 3-yr OOS blocks (stability)
  4_multiple_testing HLZ t>3, Bonferroni, Deflated Sharpe
  5_fama_macbeth    firm-level slope after size/value/momentum/beta controls

Run:
  python adapter/llm_chain.py --from-json results/llm_generated_candidates.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()

import factor_lab
import spanning
import walk_forward
import multiple_testing
import fama_macbeth
from adapter.evaluate_ic import summary as ic_summary
from adapter.manual_llm_mine import write_tree_artifacts
from llm_factor.config import path, sample


def load_candidates(from_json: str) -> list[dict]:
    data = json.loads(Path(from_json).read_text(encoding="utf-8"))
    return data["factors"] if isinstance(data, dict) else data


def main(from_json: str, outdir=None, start=None, split=None, n_trials=300) -> None:
    start = start or sample("start", "1972-01-01")
    split = split or sample("split", "2000-12-31")
    root = Path(outdir) if outdir else (path("results_root") / "llm_chain")
    root.mkdir(parents=True, exist_ok=True)

    cands = load_candidates(from_json)
    factors = {c["name"]: (c["expression"], c.get("rationale", "")) for c in cands}
    exprs = {c["name"]: c["expression"] for c in cands}
    print(f"candidates: {len(factors)}  ->  {root}")

    # 1. strict gate + per-factor charts/json
    print("\n########## 1. factor_lab (strict gate) ##########", flush=True)
    _, fl = factor_lab.run_report(factors, outdir=root / "1_factor_lab",
                                  start=start, split=split, update_library=False)

    # per-factor derivation + formula trees
    rows = []
    for c in cands:
        m = {}
        try:
            m = ic_summary(c["expression"], start=start)
        except Exception:
            pass
        rows.append({**c, "family": c.get("source", "llm"),
                     "IC": m.get("IC", float("nan")), "IC_t": m.get("IC_t", float("nan")),
                     "LS_SR": m.get("LS_SR", float("nan"))})
    write_tree_artifacts(rows, tree_dir=root / "reports_trees",
                         formula_tree_dir=root / "reports_formula_trees")

    # 2..5 deep chain (run on all candidates for complete tables)
    print("\n########## 2. spanning (vs components + Kelly zoo) ##########", flush=True)
    spanning.run_spanning(exprs, outdir=root / "2_spanning", start=start, split=split)

    print("\n########## 3. walk-forward ##########", flush=True)
    walk_forward.run_walk_forward(exprs, outdir=root / "3_walk_forward", start=start)

    print("\n########## 4. multiple testing ##########", flush=True)
    multiple_testing.run_haircuts(exprs, n_trials=n_trials, outdir=root / "4_multiple_testing", start=start)

    print("\n########## 5. Fama-MacBeth ##########", flush=True)
    fama_macbeth.run_fama_macbeth(exprs, outdir=root / "5_fama_macbeth", start=start)

    fl.to_csv(root / "gate_summary.csv", index=False)
    n_pass = int((fl["verdict"] == "PASS").sum()) if len(fl) else 0
    print(f"\nDONE -> {root}\n  gate PASS: {n_pass}/{len(factors)}  (deep-chain tables in 2_..5_ folders)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--start", default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--n-trials", type=int, default=300)
    args = ap.parse_args()
    main(args.from_json, outdir=args.outdir, start=args.start, split=args.split, n_trials=args.n_trials)

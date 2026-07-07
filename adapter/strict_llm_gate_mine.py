# -*- coding: utf-8 -*-
"""Mine LLM-style factors until the strict asset-pricing gate has 100 PASS rows.

Unlike manual_llm_mine.py, "valid" here means factor_lab verdict == PASS:
economic rationale, value-weighted FF5+UMD alpha significant in full sample and
OOS, monotone deciles, and OOS IC sign persistence.

Run:
  python adapter/strict_llm_gate_mine.py --target-pass 100 --max-gate 400
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()

import factor_lab
from adapter.evaluate_ic import summary as ic_summary
from adapter.manual_llm_mine import _rank, _z, candidate_bank, write_tree_artifacts
from adapter.sp500_loader import compute_factor
from llm_factor.config import path, sample
from llm_factor.ledger import CandidateLedger


OUTDIR = path("results_root") / "manual_llm_diverse_pass_100"
GATE_DIR = OUTDIR / "gate"
TREE_DIR = OUTDIR / "trees"
FORMULA_TREE_DIR = OUTDIR / "formula_trees"
PROGRESS = OUTDIR / "progress.json"
PASS_CSV = OUTDIR / "passed_factors.csv"
SCREENED_CSV = OUTDIR / "screened_summary.csv"
FEEDBACK_JSONL = OUTDIR / "llm_feedback.jsonl"
FEEDBACK_MD = OUTDIR / "llm_feedback.md"


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    return s[:120] or "factor"


def _add(candidates: list[dict], name: str, expr: str, rationale: str, family: str) -> None:
    candidates.append({
        "name": _safe_name(name),
        "expression": expr,
        "rationale": rationale,
        "family": family,
    })


def structure_signature(expr: str) -> str:
    """Signature that treats pure window changes as the same formula family."""
    sig = re.sub(r",\s*\d+\)", ", W)", expr)
    sig = re.sub(r"\b\d+(\.\d+)?\b", "N", sig)
    sig = re.sub(r"\s+", "", sig).upper()
    return sig


def strict_candidate_bank() -> list[dict]:
    """Large, deterministic LLM-style pool biased toward economically plausible PASS families."""
    candidates = list(candidate_bank())

    mispricing = "$mispricing_perf + $mispricing_mgmt"
    issues = ["$eqnetis_at", "$dbnetis_at", "$chcsho_12m", "$eqnpo_12m"]
    growths = ["$at_gr1", "$sale_gr1", "$noa_at", "$chcsho_12m"]
    qualities = ["$gp_at", "$op_at", "$qmj_prof", "$ni_be", "$at_turnover"]
    values = ["$be_me", "$at_me", "$bev_mev"]
    risks = ["$ivol_ff3_21d", "$beta_60m", "$rvol_21d", "$rmax5_21d"]
    moms = ["$ret_12_1", "$ret_6_1", "$resff3_12_1"]

    for wm in [3, 6, 12, 24]:
        mis_ts = f"TS_MEAN($mispricing_perf, {wm}) + TS_MEAN($mispricing_mgmt, {wm})"
        for issue in issues:
            for wi in [3, 6, 12, 24, 36]:
                issue_ts = f"TS_MEAN({issue}, {wi})"
                for growth in growths:
                    _add(
                        candidates,
                        f"strict_mispr_fin_{wm}_{issue[1:]}_{wi}_{growth[1:]}",
                        f"{_rank(mis_ts)} - {_rank(issue_ts)} - {_rank(growth)}",
                        "Persistent mispricing is more likely to reverse among firms with restrained external financing and investment.",
                        "strict_mispricing_financing",
                    )
                    for q in qualities[:4]:
                        _add(
                            candidates,
                            f"strict_mispr_fin_q_{wm}_{issue[1:]}_{wi}_{growth[1:]}_{q[1:]}",
                            f"{_rank(mis_ts)} - {_rank(issue_ts)} - {_rank(growth)} + {_rank(q)}",
                            "Mispricing reversal should be cleaner when low issuance and low growth are supported by profitability.",
                            "strict_mispricing_financing_quality",
                        )

    for issue in issues:
        for w in [3, 6, 12, 24, 36]:
            for mom in moms:
                base = f"-{_rank(f'TS_MEAN({issue}, {w})')} - {_rank(f'DELTA({issue}, {w})')} + {_rank(mom)} - {_rank('$ret_1_0')}"
                _add(
                    candidates,
                    f"strict_issuance_change_mom_{issue[1:]}_{w}_{mom[1:]}",
                    base,
                    "Low persistent issuance and falling issuance identify disciplined firms; momentum and short-term reversal capture delayed price adjustment.",
                    "strict_issuance_momentum",
                )
                for q in qualities[:4]:
                    _add(
                        candidates,
                        f"strict_issuance_change_mom_q_{issue[1:]}_{w}_{mom[1:]}_{q[1:]}",
                        f"{base} + {_rank(q)}",
                        "Issuance discipline is strengthened when the firm also shows real profitability or operating quality.",
                        "strict_issuance_momentum_quality",
                    )

    for q in qualities:
        for v in values:
            for issue in issues:
                _add(
                    candidates,
                    f"strict_value_quality_issue_{v[1:]}_{q[1:]}_{issue[1:]}",
                    f"{_rank(v)} + {_rank(q)} - {_rank(issue)} - {_rank('$ret_1_0')}",
                    "Cheap profitable firms with low issuance and short-term reversal control combine value, quality, and financing discipline.",
                    "strict_value_quality_issuance",
                )
                _add(
                    candidates,
                    f"strict_value_quality_product_{v[1:]}_{q[1:]}_{issue[1:]}",
                    f"{_rank(f'{_z(v)} * {_z(q)}')} - {_rank(issue)} - {_rank('$ret_1_0')}",
                    "The multiplicative term requires value and quality to reinforce each other before applying an issuance discipline filter.",
                    "strict_value_quality_interaction",
                )

    for q in qualities:
        for growth in growths:
            for v in values:
                _add(
                    candidates,
                    f"strict_profit_to_growth_{q[1:]}_{growth[1:]}_{v[1:]}",
                    f"{_rank(f'{q} / (ABS({growth}) + 1)')} + {_rank(v)} - {_rank('$eqnetis_at')}",
                    "Profitability per unit of growth separates efficient firms from firms expanding assets or shares aggressively.",
                    "strict_profitability_efficiency",
                )

    for risk in risks:
        for w in [6, 12, 24, 36]:
            _add(
                candidates,
                f"strict_risk_scaled_mispr_fin_{risk[1:]}_{w}",
                f"{_rank(f'({mispricing}) / (TS_STD($return, {w}) + 1)')} - {_rank(risk)} - {_rank('$eqnetis_at')}",
                "Mispricing signals scaled away from high realized and idiosyncratic risk should be more investable.",
                "strict_risk_scaled_mispricing",
            )
            _add(
                candidates,
                f"strict_risk_scaled_value_quality_{risk[1:]}_{w}",
                f"{_rank(f'($be_me + $gp_at) / (TS_STD($return, {w}) + 1)')} - {_rank(risk)} - {_rank('$eqnetis_at')}",
                "Value and profitability are more credible when not merely compensation for high realized or idiosyncratic risk.",
                "strict_risk_scaled_quality",
            )

    seen = set()
    out = []
    for c in candidates:
        if c["expression"] in seen:
            continue
        seen.add(c["expression"])
        out.append(c)
    return out


def interleave_by_family(candidates: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for c in candidates:
        buckets.setdefault(c.get("family", "unknown"), []).append(c)
    families = sorted(buckets, key=lambda f: len(buckets[f]), reverse=True)
    out = []
    while families:
        nxt = []
        for fam in families:
            if buckets[fam]:
                out.append(buckets[fam].pop(0))
            if buckets[fam]:
                nxt.append(fam)
        families = nxt
    return out


_rank_cache: dict[str, pd.Series] = {}


def _ranked_factor(expr: str) -> pd.Series:
    if expr not in _rank_cache:
        f = compute_factor(expr).replace([np.inf, -np.inf], np.nan).dropna()
        dates = f.index.get_level_values("datetime")
        _rank_cache[expr] = f.groupby(dates).rank(pct=True)
    return _rank_cache[expr]


def mean_monthly_rank_corr(expr_a: str, expr_b: str) -> float:
    a = _ranked_factor(expr_a)
    b = _ranked_factor(expr_b)
    d = pd.DataFrame({"a": a, "b": b}).dropna()
    if d.empty:
        return float("nan")

    def corr(g):
        if len(g) < 10:
            return np.nan
        return g["a"].corr(g["b"])

    c = d.groupby(level="datetime").apply(corr).dropna()
    return float(c.abs().mean()) if len(c) else float("nan")


def diversity_check(candidate: dict, passed: list[dict], max_corr: float, max_per_family: int) -> tuple[bool, dict]:
    sig = structure_signature(candidate["expression"])
    used_sigs = {p.get("structure_signature") or structure_signature(p["expression"]) for p in passed}
    if sig in used_sigs:
        return False, {"reason": "structure_duplicate_window_only", "structure_signature": sig}

    family_count = sum(1 for p in passed if p.get("family") == candidate.get("family"))
    if family_count >= max_per_family:
        return False, {
            "reason": "family_quota",
            "family": candidate.get("family"),
            "family_count": family_count,
            "max_per_family": max_per_family,
        }

    corrs = []
    for p in passed:
        c = mean_monthly_rank_corr(candidate["expression"], p["expression"])
        if c == c:
            corrs.append((p["name"], c))
    if corrs:
        best_name, best_corr = max(corrs, key=lambda x: x[1])
        if best_corr >= max_corr:
            return False, {
                "reason": "high_factor_rank_correlation",
                "nearest_factor": best_name,
                "max_abs_monthly_rank_corr": best_corr,
                "threshold": max_corr,
                "structure_signature": sig,
            }
        return True, {
            "nearest_factor": best_name,
            "max_abs_monthly_rank_corr": best_corr,
            "structure_signature": sig,
        }
    return True, {"structure_signature": sig, "max_abs_monthly_rank_corr": 0.0}


def _feedback_text(stage: str, reason: str, metrics: dict | None = None, diversity: dict | None = None) -> str:
    metrics = metrics or {}
    diversity = diversity or {}
    if stage == "prefilter":
        return (
            "Reject before full gate: quick IC screen is too weak. The next proposal needs a clearer "
            "cross-sectional return prediction, not an algebraic variation."
        )
    if stage == "diversity":
        if reason == "structure_duplicate_window_only":
            return "Reject for novelty: this mainly changes a window or numeric constant. Change fields, operators, or economic mechanism."
        if reason == "family_quota":
            return "Reject for portfolio diversity: this economic family is already saturated. Move to a different anomaly mechanism."
        if reason == "high_factor_rank_correlation":
            return (
                f"Reject for redundancy: too correlated with {diversity.get('nearest_factor')} "
                f"(abs monthly rank corr={diversity.get('max_abs_monthly_rank_corr', float('nan')):.2f}). "
                "Use different source fields or a genuinely different interaction."
            )
        return "Reject for novelty/diversity. Avoid near-duplicates of selected factors."
    failed = metrics.get("failed_checks", [])
    hints = []
    if any("alpha_sig_full" in x for x in failed):
        hints.append("full-sample VW FF5+UMD alpha is too weak")
    if any("alpha_sig_oos" in x for x in failed):
        hints.append("OOS VW FF5+UMD alpha does not survive")
    if "monotone_full" in failed:
        hints.append("decile portfolio is not monotone")
    if "oos_ic_same_sign" in failed:
        hints.append("OOS IC changes sign or vanishes")
    detail = "; ".join(hints) if hints else "strict empirical checks failed"
    return f"Reject after full gate: {detail}. Next proposal should change the economic mechanism, not just tune a window."


def append_feedback(candidate: dict, stage: str, decision: str, metrics: dict | None = None,
                    diversity: dict | None = None, error: str | None = None) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    metrics = metrics or {}
    diversity = diversity or {}
    reason = diversity.get("reason") or metrics.get("reason") or decision
    rec = {
        "name": candidate.get("name"),
        "family": candidate.get("family"),
        "expression": candidate.get("expression"),
        "stage": stage,
        "decision": decision,
        "reason": reason,
        "metrics": metrics,
        "diversity": diversity,
        "error": error,
        "llm_feedback": _feedback_text(stage, reason, metrics=metrics, diversity=diversity),
    }
    with FEEDBACK_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def write_feedback_md() -> None:
    if not FEEDBACK_JSONL.exists():
        return
    rows = []
    with FEEDBACK_JSONL.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    counts = pd.Series([r["reason"] for r in rows]).value_counts() if rows else pd.Series(dtype=int)
    lines = [
        "# LLM failure feedback",
        "",
        "Use this as negative feedback for the next LLM generation round.",
        "",
        "## Failure counts",
        "",
        "| Reason | Count |",
        "|---|---:|",
    ]
    for reason, n in counts.items():
        lines.append(f"| {reason} | {int(n)} |")
    lines += ["", "## Recent actionable feedback", ""]
    for r in rows[-40:]:
        lines += [
            f"### {r['name']} [{r['stage']} / {r['decision']}]",
            f"- **Expr:** `{r['expression']}`",
            f"- **Feedback:** {r['llm_feedback']}",
            "",
        ]
    FEEDBACK_MD.write_text("\n".join(lines), encoding="utf-8")


def load_progress() -> dict:
    if not PROGRESS.exists():
        return {"seen": [], "passed": [], "screened": []}
    return json.loads(PROGRESS.read_text(encoding="utf-8"))


def save_progress(progress: dict) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")


def _flat_gate_row(res: dict, family: str) -> dict:
    f, te = res["full"], res["test"]
    av = f["vw"]["alphas"] or {}
    ae = f["ew"]["alphas"] or {}
    atv = te["vw"]["alphas"] or {}
    a6v = av.get("FF5+UMD") or {}
    a6e = ae.get("FF5+UMD") or {}
    a6tv = atv.get("FF5+UMD") or {}
    return {
        "name": res["name"],
        "family": family,
        "verdict": res["verdict"],
        "expr": res["expr"],
        "IC_full": f["IC"],
        "IC_t_full": f["IC_t"],
        "mono": f["mono"],
        "VW_FF5UMDa_ann": a6v.get("alpha_ann"),
        "VW_FF5UMDa_t": a6v.get("alpha_t"),
        "EW_FF5UMDa_t": a6e.get("alpha_t"),
        "IC_test": te["IC"],
        "VW_FF5UMDa_t_test": a6tv.get("alpha_t"),
        "checks": json.dumps(res["checks"], ensure_ascii=False),
    }


def _write_csvs(screened: list[dict], passed: list[dict]) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if screened:
        pd.DataFrame(screened).to_csv(SCREENED_CSV, index=False)
    pass_rows = []
    for r in passed:
        pass_rows.append({
            "name": r["name"],
            "family": r.get("family", ""),
            "expression": r["expression"],
            "rationale": r["rationale"],
            "IC": r.get("IC"),
            "IC_t": r.get("IC_t"),
            "ICIR": r.get("ICIR"),
            "LS_SR": r.get("LS_SR"),
            "VW_FF5UMDa_t": r.get("VW_FF5UMDa_t"),
            "VW_FF5UMDa_t_test": r.get("VW_FF5UMDa_t_test"),
            "structure_signature": r.get("structure_signature"),
            "max_abs_monthly_rank_corr": r.get("max_abs_monthly_rank_corr"),
            "nearest_factor": r.get("nearest_factor"),
        })
    if pass_rows:
        pd.DataFrame(pass_rows).sort_values("VW_FF5UMDa_t", ascending=False).to_csv(PASS_CSV, index=False)


def main(
    target_pass=100,
    max_gate=400,
    min_prefilter_ic_t=2.0,
    start=None,
    split=None,
    max_corr=0.75,
    max_per_family=10,
) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    start = start or sample("start", "1972-01-01")
    split = split or sample("split", "2000-12-31")
    progress = load_progress()
    seen = set(progress.get("seen", []))
    passed_by_expr = {r["expression"]: r for r in progress.get("passed", [])}
    screened = list(progress.get("screened", []))
    ledger = CandidateLedger("strict_llm_gate_mine_100", root=OUTDIR)

    gated_this_run = 0
    prefilter_rejected = 0
    bank = interleave_by_family([c for c in strict_candidate_bank() if c["expression"] not in seen])

    for c in bank:
        if len(passed_by_expr) >= target_pass or gated_this_run >= max_gate:
            break
        seen.add(c["expression"])
        base = {
            "source": "strict_llm_gate_mine",
            "status_rule": "factor_lab verdict == PASS",
            **c,
        }
        try:
            quick = ic_summary(c["expression"], start=start)
        except Exception as exc:
            ledger.append(**base, status="error", stage="prefilter", error=str(exc))
            append_feedback(c, "prefilter", "error", error=str(exc))
            continue
        if quick["IC"] <= 0 or quick["IC_t"] < min_prefilter_ic_t:
            prefilter_rejected += 1
            ledger.append(**base, status="rejected", stage="prefilter", metrics=quick)
            append_feedback(c, "prefilter", "rejected", metrics=quick)
            continue

        gated_this_run += 1
        try:
            res = factor_lab.evaluate_factor_full(c["name"], c["expression"], c["rationale"], start=start, split=split)
            row = _flat_gate_row(res, c["family"])
            row["failed_checks"] = [k for k, v in res["checks"].items() if not v]
            screened.append(row)
            ledger.append(**base, status=res["verdict"].lower(), stage="strict_gate", metrics=row, checks=res["checks"])
            if res["verdict"] == "PASS":
                is_diverse, div = diversity_check(c, list(passed_by_expr.values()), max_corr, max_per_family)
                if not is_diverse:
                    ledger.append(**base, status="rejected", stage="diversity", metrics=row, diversity=div)
                    append_feedback(c, "diversity", "rejected", metrics=row, diversity=div)
                    print(f"REJECT diversity: {c['name']}  {div['reason']}", flush=True)
                    continue
                plot_res = dict(res)
                factor_lab.plot_factor(plot_res, GATE_DIR)
                json_res = {k: v for k, v in res.items() if k != "_plot"}
                (GATE_DIR / f"{c['name']}.json").write_text(
                    json.dumps(json_res, indent=2, default=float, ensure_ascii=False),
                    encoding="utf-8",
                )
                passed_by_expr[c["expression"]] = {
                    **c,
                    **quick,
                    "VW_FF5UMDa_t": row["VW_FF5UMDa_t"],
                    "VW_FF5UMDa_t_test": row["VW_FF5UMDa_t_test"],
                    **div,
                }
                print(
                    f"PASS {len(passed_by_expr):3d}/{target_pass}: {c['name']}  "
                    f"full_t={row['VW_FF5UMDa_t']:+.2f} oos_t={row['VW_FF5UMDa_t_test']:+.2f} "
                    f"max_corr={div.get('max_abs_monthly_rank_corr', 0):.2f}",
                    flush=True,
                )
            else:
                append_feedback(c, "strict_gate", "failed", metrics=row)
                print(f"FAIL gate {gated_this_run:3d}: {c['name']}  full_t={row['VW_FF5UMDa_t']:+.2f} oos_t={row['VW_FF5UMDa_t_test']:+.2f}", flush=True)
        except Exception as exc:
            ledger.append(**base, status="error", stage="strict_gate", error=str(exc), metrics=quick)
            append_feedback(c, "strict_gate", "error", metrics=quick, error=str(exc))

        progress = {
            "target_pass": target_pass,
            "strict_pass_count": len(passed_by_expr),
            "max_gate": max_gate,
            "min_prefilter_ic_t": min_prefilter_ic_t,
            "max_corr": max_corr,
            "max_per_family": max_per_family,
            "start": start,
            "split": split,
            "seen": sorted(seen),
            "passed": list(passed_by_expr.values()),
            "screened": screened,
            "candidate_bank_size": len(strict_candidate_bank()),
            "gated_this_run": gated_this_run,
            "prefilter_rejected_this_run": prefilter_rejected,
            "ledger": str(ledger.path),
        }
        save_progress(progress)
        _write_csvs(screened, list(passed_by_expr.values()))

    passed = list(passed_by_expr.values())
    write_tree_artifacts(passed, tree_dir=TREE_DIR, formula_tree_dir=FORMULA_TREE_DIR)
    write_feedback_md()
    _write_csvs(screened, passed)
    if screened:
        pd.DataFrame(screened).to_csv(GATE_DIR / "summary.csv", index=False)
    readme = [
        "# Strict LLM PASS mining",
        "",
        f"- Target PASS factors: {target_pass}",
        f"- Current PASS factors: {len(passed)}",
        f"- Strict gate attempts this run: {gated_this_run}",
        f"- Prefilter rejected this run: {prefilter_rejected}",
        f"- Max absolute monthly rank correlation allowed: {max_corr}",
        f"- Max factors per family: {max_per_family}",
        "",
        "A PASS factor must satisfy the same factor_lab gate used by the thesis reports.",
        "A final factor must also pass structural and correlation diversity checks.",
        "Trees are written only for final PASS factors.",
        "",
        "Feedback for the next LLM generation round is stored in `llm_feedback.jsonl` and `llm_feedback.md`.",
    ]
    (OUTDIR / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(f"OUTDIR={OUTDIR}")
    print(f"PASS={len(passed)}/{target_pass}  gated_this_run={gated_this_run} prefilter_rejected_this_run={prefilter_rejected}")
    print(f"LEDGER={ledger.path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-pass", type=int, default=100)
    ap.add_argument("--max-gate", type=int, default=400)
    ap.add_argument("--min-prefilter-ic-t", type=float, default=2.0)
    ap.add_argument("--max-corr", type=float, default=0.75)
    ap.add_argument("--max-per-family", type=int, default=10)
    ap.add_argument("--start", default=None)
    ap.add_argument("--split", default=None)
    args = ap.parse_args()
    main(
        target_pass=args.target_pass,
        max_gate=args.max_gate,
        min_prefilter_ic_t=args.min_prefilter_ic_t,
        start=args.start,
        split=args.split,
        max_corr=args.max_corr,
        max_per_family=args.max_per_family,
    )

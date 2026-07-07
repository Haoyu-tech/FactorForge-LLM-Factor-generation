# -*- coding: utf-8 -*-
"""Manual LLM-style factor mining with resumable progress.

This is the "Codex as LLM" mining loop: generate economically interpretable
candidate expressions under the configured fast_full grammar, evaluate RankIC,
and keep a durable ledger/progress file. It does not call any external LLM API.

Default validity rule:
  accepted and effective = unique, computable, IC > 0, IC_t >= 2.0.

Run:
  python adapter/manual_llm_mine.py --target 100 --batch-size 120
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()

from adapter.evaluate_ic import summary
from adapter.gp_viz import write_formula_tree
from llm_factor.config import path, sample
from llm_factor.ledger import CandidateLedger


OUTDIR = path("results_root") / "manual_llm_mining_100"
PROGRESS = OUTDIR / "progress.json"
CSV_PATH = OUTDIR / "valid_factors.csv"
TREE_DIR = OUTDIR / "trees"
FORMULA_TREE_DIR = OUTDIR / "formula_trees"


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    return s[:120] or "factor"


def _fields(expr: str) -> list[str]:
    return sorted(set(re.findall(r"\$[A-Za-z0-9_]+", expr)))


def _operators(expr: str) -> list[str]:
    names = [
        "RANK", "ZSCORE", "SCALE", "TS_MEAN", "TS_STD", "TS_ZSCORE",
        "TS_MAX", "TS_MIN", "TS_SUM", "DELTA", "DELAY", "TS_PCTCHANGE",
        "ABS", "SIGN",
    ]
    ops = [op for op in names if re.search(rf"\b{op}\s*\(", expr)]
    for sym, label in [("*", "MULTIPLY"), ("/", "DIVIDE"), ("+", "ADD"), ("-", "SUBTRACT")]:
        if sym in expr:
            ops.append(label)
    return ops


def _structure_type(expr: str) -> str:
    tags = []
    if "*" in expr:
        tags.append("multiplicative interaction")
    if "/" in expr:
        tags.append("ratio / risk scaling")
    if "TS_" in expr or "DELTA(" in expr or "DELAY(" in expr:
        tags.append("time-series transform")
    if not tags:
        tags.append("rank-sum composite")
    return ", ".join(tags)


def _mermaid_label(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")


def write_tree_artifacts(valid: list[dict], tree_dir: Path | None = None, formula_tree_dir: Path | None = None) -> None:
    """Write one Mermaid markdown tree and one PNG tree per valid factor."""
    tree_dir = tree_dir or TREE_DIR
    formula_tree_dir = formula_tree_dir or FORMULA_TREE_DIR
    tree_dir.mkdir(parents=True, exist_ok=True)
    formula_tree_dir.mkdir(parents=True, exist_ok=True)
    index = ["# Factor Derivation Trees", ""]
    formula_index = ["# LLM Formula Parse Trees", ""]
    for row in sorted(valid, key=lambda x: x.get("IC_t", 0), reverse=True):
        name = row["name"]
        expr = row["expression"]
        stem = _safe_name(name)
        fields = _fields(expr)
        ops = _operators(expr)
        structure = _structure_type(expr)
        metrics = f"IC={row.get('IC', float('nan')):+.4f}, IC_t={row.get('IC_t', float('nan')):+.2f}, LS_SR={row.get('LS_SR', float('nan')):+.2f}"
        md_path = tree_dir / f"{stem}.md"
        png_path = tree_dir / f"{stem}.png"

        field_nodes = "\n".join(
            f'  F{i}["{_mermaid_label(f)}"] --> T' for i, f in enumerate(fields, 1)
        )
        op_nodes = "\n".join(
            f'  O{i}["{_mermaid_label(op)}"] --> T' for i, op in enumerate(ops, 1)
        )
        md = [
            f"# {name}",
            "",
            "```mermaid",
            "flowchart TD",
            f'  H["Economic hypothesis: {_mermaid_label(row.get("rationale", ""))}"] --> S["Structure: {_mermaid_label(structure)}"]',
            f'  S --> T["Transform / combine signals"]',
            field_nodes,
            op_nodes,
            f'  T --> E["Expression: {_mermaid_label(expr)}"]',
            f'  E --> M["Metrics: {metrics}"]',
            "```",
            "",
            f"- **Family:** `{row.get('family', '')}`",
            f"- **Structure:** {structure}",
            f"- **Fields:** `{', '.join(fields)}`",
            f"- **Operators:** `{', '.join(ops)}`",
            f"- **Expression:** `{expr}`",
            f"- **Metrics:** {metrics}",
        ]
        md_path.write_text("\n".join(md), encoding="utf-8")
        _write_tree_png(png_path, row, fields, ops, structure, metrics)
        index.append(f"- [{name}]({md_path.name}) - [{png_path.name}]({png_path.name})")

        formula_md = formula_tree_dir / f"{stem}.md"
        formula_png = formula_tree_dir / f"{stem}.png"
        write_formula_tree(
            expr,
            formula_md,
            formula_png,
            title=f"LLM Formula Tree: {name}",
        )
        formula_index.append(f"- [{name}]({formula_md.name}) - [{formula_png.name}]({formula_png.name})")
    (tree_dir / "README.md").write_text("\n".join(index), encoding="utf-8")
    (formula_tree_dir / "README.md").write_text("\n".join(formula_index), encoding="utf-8")


def _write_tree_png(path: Path, row: dict, fields: list[str], ops: list[str], structure: str, metrics: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from textwrap import wrap

    def box(ax, x, y, text, fc="#f7f7f7", fs=8, width=32):
        text = str(text).replace("$", r"\$")
        label = "\n".join(wrap(text, width=width))
        ax.text(
            x, y, label, ha="center", va="center", fontsize=fs,
            bbox=dict(boxstyle="round,pad=0.35", fc=fc, ec="#555555", lw=0.8),
        )

    def arrow(ax, x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=0.8, color="#555555"))

    fig, ax = plt.subplots(figsize=(13, 8))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    title = row["name"]
    ax.text(0.5, 0.965, title, ha="center", va="top", fontsize=12, fontweight="bold")

    box(ax, 0.5, 0.85, f"Hypothesis: {row.get('rationale', '')}", fc="#e8f1fb", width=74)
    box(ax, 0.5, 0.68, f"Structure: {structure}", fc="#fff4db", width=58)
    arrow(ax, 0.5, 0.81, 0.5, 0.72)

    left_text = "Fields:\n" + "\n".join(fields)
    right_text = "Operators:\n" + "\n".join(ops)
    box(ax, 0.22, 0.48, left_text, fc="#eef8ec", width=28)
    box(ax, 0.78, 0.48, right_text, fc="#f9ecec", width=28)
    box(ax, 0.5, 0.48, "Transform / combine signals", fc="#f7f7f7", width=32)
    arrow(ax, 0.5, 0.64, 0.5, 0.53)
    arrow(ax, 0.32, 0.48, 0.42, 0.48)
    arrow(ax, 0.68, 0.48, 0.58, 0.48)

    box(ax, 0.5, 0.27, f"Expression: {row['expression']}", fc="#f3effa", width=82)
    arrow(ax, 0.5, 0.43, 0.5, 0.32)
    box(ax, 0.5, 0.10, metrics, fc="#eaf7f7", width=54)
    arrow(ax, 0.5, 0.22, 0.5, 0.14)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _rank(x: str) -> str:
    return f"RANK({x})"


def _z(x: str) -> str:
    return f"ZSCORE({x})"


def candidate_bank() -> list[dict]:
    """Deterministic LLM-style candidate bank, ordered from more to less plausible."""
    candidates: list[dict] = []

    def add(name, expr, rationale, family):
        candidates.append({
            "name": name,
            "expression": expr,
            "rationale": rationale,
            "family": family,
        })

    # Persistent mispricing + disciplined financing/investment.
    for w_mis in (3, 6, 12):
        for w_fin in (6, 12, 24):
            add(
                f"mispr_ts_fin_disc_{w_mis}_{w_fin}",
                f"{_rank(f'TS_MEAN($mispricing_perf, {w_mis}) + TS_MEAN($mispricing_mgmt, {w_mis})')} "
                f"- {_rank(f'TS_MEAN($eqnetis_at, {w_fin})')} - {_rank('$at_gr1')}",
                "Persistent mispricing should earn stronger reversals when equity issuance and asset growth are restrained.",
                "mispricing_financing_ts",
            )
            add(
                f"mispr_ts_fin_qual_{w_mis}_{w_fin}",
                f"{_rank(f'TS_MEAN($mispricing_perf, {w_mis}) + TS_MEAN($mispricing_mgmt, {w_mis})')} "
                f"- {_rank(f'TS_MEAN($eqnetis_at, {w_fin})')} - {_rank('$at_gr1')} + {_rank('$gp_at')}",
                "Persistent mispricing is more credible when supported by profitability and capital discipline.",
                "mispricing_financing_ts",
            )

    # Issuance level/change plus momentum/reversal control.
    for issue in ("$eqnetis_at", "$dbnetis_at", "$chcsho_12m"):
        for w in (6, 12, 24):
            add(
                f"issuance_level_change_mom_{issue[1:]}_{w}",
                f"-{_rank(f'TS_MEAN({issue}, {w})')} - {_rank(f'DELTA({issue}, {w})')} "
                f"+ {_rank('$ret_12_1')} - {_rank('$ret_1_0')}",
                "Both persistent financing and rising financing are negative; momentum and short-term reversal control delayed price adjustment.",
                "issuance_momentum_ts",
            )
            add(
                f"issuance_disc_quality_mom_{issue[1:]}_{w}",
                f"-{_rank(f'TS_MEAN({issue}, {w})')} + {_rank('$ret_12_1')} - {_rank('$ret_1_0')} + {_rank('$op_at')}",
                "Low financing, profitability, and momentum combine capital discipline with underreaction.",
                "issuance_momentum_ts",
            )

    # Profitability per unit of investment/growth, with value and low issuance.
    profs = ["$gp_at", "$op_at", "$qmj_prof", "$ni_be"]
    growths = ["$at_gr1", "$sale_gr1", "$noa_at", "$chcsho_12m"]
    for p in profs:
        for g in growths:
            add(
                f"profit_to_growth_value_{p[1:]}_{g[1:]}",
                f"{_rank(f'{p} / (ABS({g}) + 1)')} + {_rank('$be_me')} - {_rank('$eqnetis_at')}",
                "Profitability scaled by growth separates efficient value firms from firms expanding assets or shares aggressively.",
                "profitability_efficiency_ratio",
            )
            value_profit_product = f"({_z('$be_me')} * {_z(p)})"
            add(
                f"value_profit_growth_product_{p[1:]}_{g[1:]}",
                f"{_rank(value_profit_product)} - {_rank(g)} - {_rank('$eqnetis_at')}",
                "Value works better when paired with profitability, low growth pressure, and low equity issuance.",
                "profitability_efficiency_interaction",
            )

    # Risk-scaled value/momentum/mispricing.
    numerators = [
        ("mispricing", "$mispricing_perf + $mispricing_mgmt"),
        ("value_mom", "$be_me + $ret_12_1 - $ret_1_0"),
        ("quality_mom", "$gp_at + $ret_12_1 - $ret_1_0"),
        ("value_quality", "$be_me + $gp_at"),
    ]
    for nm, num in numerators:
        for w in (6, 12, 24):
            add(
                f"risk_scaled_{nm}_{w}",
                f"{_rank(f'({num}) / TS_STD($return, {w})')} - {_rank('$ivol_ff3_21d')}",
                "Signals scaled by realized volatility should reduce noisy high-risk exposure.",
                "risk_scaled_ratio",
            )
            add(
                f"risk_scaled_{nm}_fin_{w}",
                f"{_rank(f'({num}) / TS_STD($return, {w})')} - {_rank('$ivol_ff3_21d')} - {_rank('$eqnetis_at')}",
                "Risk-scaled signals are strengthened by low idiosyncratic risk and low equity issuance.",
                "risk_scaled_ratio",
            )

    # Multiplicative economic interactions.
    interactions = [
        ("mispr_gp", "$mispricing_mgmt", "$gp_at", "$eqnetis_at"),
        ("mispr_value", "$mispricing_perf", "$be_me", "$at_gr1"),
        ("value_safety", "$be_me", "$qmj_safety", "$beta_60m"),
        ("mom_quality", "$ret_12_1", "$qmj_prof", "$ret_1_0"),
        ("value_prof", "$be_me", "$op_at", "$eqnetis_at"),
    ]
    for nm, a, b, bad in interactions:
        add(
            f"interaction_{nm}",
            f"{_rank(f'{_z(a)} * {_z(b)}')} - {_rank(bad)}",
            "The product term asks whether two economically distinct signals reinforce each other rather than merely add linearly.",
            "multiplicative_interaction",
        )
        add(
            f"interaction_{nm}_lowrisk",
            f"{_rank(f'{_z(a)} * {_z(b)}')} - {_rank(bad)} - {_rank('$ivol_ff3_21d')}",
            "The interaction is combined with a low-risk filter to reduce fragile anomaly exposure.",
            "multiplicative_interaction",
        )

    # Trend/acceleration variants.
    trend_specs = [
        ("gp_value", "$gp_at", "$be_me", "$eqnetis_at"),
        ("op_value", "$op_at", "$be_me", "$at_gr1"),
        ("mispr_perf_issue", "$mispricing_perf", "$gp_at", "$eqnetis_at"),
        ("mispr_mgmt_issue", "$mispricing_mgmt", "$op_at", "$eqnetis_at"),
    ]
    for nm, trend, support, bad in trend_specs:
        for w in (6, 12):
            add(
                f"trend_{nm}_{w}",
                f"{_rank(f'TS_ZSCORE({trend}, {w})')} + {_rank(support)} - {_rank(bad)}",
                "A favorable trend in the core characteristic should matter more when supported by valuation or profitability and low adverse financing.",
                "trend_interaction",
            )
            add(
                f"trend_{nm}_stability_{w}",
                f"{_rank(f'TS_ZSCORE({trend}, {w})')} + {_rank(support)} - {_rank(bad)} - {_rank(f'TS_STD($return, {w})')}",
                "The trend signal is penalized when realized volatility suggests instability or noise.",
                "trend_interaction",
            )

    # Liquidity/implementation guarded signals.
    core_signals = [
        ("mispricing", "$mispricing_perf + $mispricing_mgmt"),
        ("fin_disc", "-$eqnetis_at - $at_gr1"),
        ("value_quality", "$be_me + $gp_at"),
        ("mom_value", "$ret_12_1 + $be_me"),
    ]
    for nm, sig in core_signals:
        add(
            f"liquid_{nm}",
            f"{_rank(sig)} + {_rank('$turnover_126d')} - {_rank('$bidaskhl_21d')} - {_rank('$ivol_ff3_21d')}",
            "A signal should be more credible and tradable when liquidity is high, spreads are low, and idiosyncratic risk is low.",
            "liquidity_guard",
        )

    # Classic robust composites retained for calibration.
    add(
        "financing_reversal_guard",
        f"-{_rank('$eqnetis_at')} - {_rank('$dbnetis_at')} + {_rank('$ret_12_1')} - {_rank('$ret_1_0')}",
        "Low net financing plus intermediate momentum, guarded against short-term reversal, captures disciplined capital structure and underreaction.",
        "rank_sum_calibration",
    )
    add(
        "mispr_fin_quality",
        f"{_rank('$mispricing_perf')} + {_rank('$mispricing_mgmt')} - {_rank('$eqnetis_at')} - {_rank('$at_gr1')} + {_rank('$gp_at')}",
        "Mispricing should reverse more strongly when firms also avoid equity issuance, restrain asset growth, and show profitability support.",
        "rank_sum_calibration",
    )

    # Deduplicate by expression while preserving order.
    seen = set()
    out = []
    for c in candidates:
        if c["expression"] in seen:
            continue
        seen.add(c["expression"])
        out.append(c)
    return out


def load_progress() -> dict:
    if not PROGRESS.exists():
        return {"seen": [], "valid": []}
    return json.loads(PROGRESS.read_text(encoding="utf-8"))


def save_progress(progress: dict) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")


def write_valid_csv(valid: list[dict]) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cols = ["name", "family", "expression", "rationale", "IC", "IC_t", "ICIR", "LS_SR", "LS_ret_ann", "n_months"]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in sorted(valid, key=lambda x: x.get("IC_t", 0), reverse=True):
            w.writerow({c: r.get(c, "") for c in cols})


def main(target=100, batch_size=120, min_ic_t=2.0, start=None):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    start = start or sample("start", "1972-01-01")
    progress = load_progress()
    seen = set(progress.get("seen", []))
    valid_by_expr = {r["expression"]: r for r in progress.get("valid", [])}

    ledger = CandidateLedger("manual_llm_mining_100", root=OUTDIR)
    bank = [c for c in candidate_bank() if c["expression"] not in seen]
    attempted = 0
    accepted = 0
    for c in bank:
        if len(valid_by_expr) >= target or attempted >= batch_size:
            break
        attempted += 1
        seen.add(c["expression"])
        base = {
            "source": "manual_llm_mining_100",
            "status_rule": f"IC > 0 and IC_t >= {min_ic_t}",
            **c,
        }
        try:
            m = summary(c["expression"], start=start)
            row = {**c, **m}
            if m["IC"] > 0 and m["IC_t"] >= min_ic_t:
                valid_by_expr[c["expression"]] = row
                accepted += 1
                ledger.append(**base, status="effective", metrics=m)
            else:
                ledger.append(**base, status="rejected", metrics=m)
        except Exception as exc:
            ledger.append(**base, status="error", error=str(exc))

    progress = {
        "target": target,
        "min_ic_t": min_ic_t,
        "start": start,
        "seen": sorted(seen),
        "valid": list(valid_by_expr.values()),
        "candidate_bank_size": len(candidate_bank()),
        "last_batch_attempted": attempted,
        "last_batch_accepted": accepted,
        "ledger": str(ledger.path),
    }
    save_progress(progress)
    write_valid_csv(progress["valid"])
    write_tree_artifacts(progress["valid"])

    valid = sorted(progress["valid"], key=lambda x: x.get("IC_t", 0), reverse=True)
    print(f"OUTDIR={OUTDIR}")
    print(f"LEDGER={ledger.path}")
    print(f"VALID={len(valid)}/{target}  attempted_this_batch={attempted} accepted_this_batch={accepted}")
    print(f"{'name':34} {'family':28} {'IC':>8} {'IC_t':>7} {'LS_SR':>7}  expression")
    for r in valid[:30]:
        print(f"{r['name'][:34]:34} {r['family'][:28]:28} {r['IC']:>8.4f} {r['IC_t']:>7.2f} {r['LS_SR']:>7.2f}  {r['expression']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=100)
    ap.add_argument("--batch-size", type=int, default=120)
    ap.add_argument("--min-ic-t", type=float, default=2.0)
    ap.add_argument("--start", default=None)
    args = ap.parse_args()
    main(target=args.target, batch_size=args.batch_size, min_ic_t=args.min_ic_t, start=args.start)

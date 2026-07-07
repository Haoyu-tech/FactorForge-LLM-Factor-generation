# -*- coding: utf-8 -*-
"""
Walk-forward evaluation - replaces the single 2000-12-31 split with a sequence of
expanding-window out-of-sample blocks, so a factor's OOS performance is judged on
stability across many periods, not one arbitrary cut.

Because formulaic factors have no fitted parameters, "walk-forward" here means:
roll an OOS test block forward through time and recompute, per block:
  - mean monthly RankIC,
  - value-weighted long-short return (annualised),
  - FF5+UMD alpha t (Newey-West) when the block is long enough.
Then aggregate: mean OOS IC, fraction of blocks with IC>0, t-stat of block ICs,
and the worst block - the honest "does it hold up everywhere" picture.

Run:  python adapter/walk_forward.py
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from sp500_loader import compute_factor, load_labels
from factor_lab import _ic_series, _deciles, _alphas, load_me, ROOT, _stars_txt
from llm_factor.config import sample
from llm_factor.factors import factor_exprs


def _blocks(first_oos=None, end="2025-12-31", step_years=None):
    """Expanding-window OOS blocks: [start_y, start_y+step) walking to the end."""
    first_oos = first_oos or sample("walk_forward_first_oos", "1990-01-01")
    step_years = step_years or sample("walk_forward_step_years", 3)
    start = pd.Timestamp(first_oos)
    last = pd.Timestamp(end)
    edges = []
    y = start
    while y < last:
        y2 = y + pd.DateOffset(years=step_years)
        edges.append((y, min(y2, last)))
        y = y2
    return edges


def walk_forward(expr, weighting="vw", start=None,
                 first_oos=None, step_years=None):
    start = start or sample("start", "1972-01-01")
    first_oos = first_oos or sample("walk_forward_first_oos", "1990-01-01")
    step_years = step_years or sample("walk_forward_step_years", 3)
    factor = compute_factor(expr)
    label = load_labels().reindex(factor.index)
    w = load_me().reindex(factor.index) if weighting == "vw" else None
    dt = factor.index.get_level_values("datetime")

    fold_rows = []
    for (a, b) in _blocks(first_oos, str(dt.max().date()), step_years):
        m = (dt >= a) & (dt < b)
        if m.sum() == 0:
            continue
        f, y = factor[m], label[m]
        ww = w[m] if w is not None else None
        ic = _ic_series(f, y)
        if len(ic) < 6:
            continue
        _, ls = _deciles(f, y, ww)
        al = _alphas(ls) or {}
        a6 = al.get("FF5+UMD") or {}
        fold_rows.append({
            "block": f"{a.year}-{b.year}", "n_months": int(len(ic)),
            "IC": float(ic.mean()), "LS_ann": float(ls.mean() * 12),
            "FF5UMD_a_t": a6.get("alpha_t", float("nan")),
        })
    fdf = pd.DataFrame(fold_rows)
    if fdf.empty:
        return {"folds": fdf}
    ics = fdf["IC"].values
    agg = {
        "n_blocks": len(fdf),
        "OOS_IC_mean": float(np.mean(ics)),
        "frac_IC_pos": float(np.mean(ics > 0)),
        "IC_block_t": float(np.mean(ics) / np.std(ics, ddof=1) * np.sqrt(len(ics))) if len(ics) > 1 and np.std(ics, ddof=1) > 0 else np.nan,
        "worst_block_IC": float(np.min(ics)),
        "worst_block": fdf.loc[fdf["IC"].idxmin(), "block"],
    }
    return {"folds": fdf, "agg": agg}


def run_walk_forward(factors: dict, weighting="vw", start=None,
                     first_oos=None, step_years=None, outdir=None):
    start = start or sample("start", "1972-01-01")
    first_oos = first_oos or sample("walk_forward_first_oos", "1990-01-01")
    step_years = step_years or sample("walk_forward_step_years", 3)
    outdir = Path(outdir) if outdir else ROOT / "results" / f"walkfwd_{datetime.now():%Y%m%d_%H%M%S}"
    outdir.mkdir(parents=True, exist_ok=True)
    summary, fold_dump = [], {}
    for name, expr in factors.items():
        print(f"-- {name} --  {expr}")
        wf = walk_forward(expr, weighting, start, first_oos, step_years)
        if "agg" not in wf:
            print("   (insufficient data)"); continue
        a = wf["agg"]; a["name"] = name
        summary.append(a)
        fold_dump[name] = wf["folds"]
        ic_str = " ".join(f"{r.block}:{r.IC:+.3f}" for r in wf["folds"].itertuples())
        print(f"   OOS IC mean={a['OOS_IC_mean']:+.4f}  pos={a['frac_IC_pos']*100:.0f}%  "
              f"block-t={a['IC_block_t']:+.2f}  worst={a['worst_block_IC']:+.3f}({a['worst_block']})")
        print(f"      blocks: {ic_str}")
    sdf = pd.DataFrame(summary)[["name", "n_blocks", "OOS_IC_mean", "frac_IC_pos",
                                 "IC_block_t", "worst_block_IC", "worst_block"]]
    sdf.to_csv(outdir / "walk_forward.csv", index=False)
    # per-factor fold detail
    with open(outdir / "walk_forward_folds.csv", "w", encoding="utf-8") as fh:
        for name, fdf in fold_dump.items():
            fh.write(f"# {name}\n"); fdf.to_csv(fh, index=False); fh.write("\n")
    _write_md(sdf, fold_dump, outdir, weighting, step_years)
    print(f"\nwalk-forward tables -> {outdir}")
    return outdir, sdf


def _write_md(sdf, fold_dump, outdir, weighting, step_years):
    L = ["# Walk-forward evaluation",
         f"_{weighting.upper()} long-short, expanding-window OOS blocks of {step_years} years. "
         f"block-t = t-stat of the block-mean ICs; frac_pos = share of blocks with IC>0._\n",
         "## Aggregate", "",
         "| Factor | #blocks | OOS IC mean | frac IC>0 | block-t | worst block IC |",
         "|---|---|---|---|---|---|"]
    for _, r in sdf.iterrows():
        L.append(f"| {r['name']} | {int(r['n_blocks'])} | {r['OOS_IC_mean']:+.4f} | "
                 f"{r['frac_IC_pos']*100:.0f}% | {r['IC_block_t']:+.2f}{_stars_txt(r['IC_block_t'])} | "
                 f"{r['worst_block_IC']:+.3f} ({r['worst_block']}) |")
    L += ["", "## Per-block RankIC", ""]
    for name, fdf in fold_dump.items():
        cells = " | ".join(f"{r.IC:+.3f}" for r in fdf.itertuples())
        hdr = " | ".join(r.block for r in fdf.itertuples())
        L += [f"**{name}**", "", "| " + hdr + " |", "|" + "---|" * len(fdf),
              "| " + cells + " |", ""]
    (outdir / "walk_forward.md").write_text("\n".join(L), encoding="utf-8")


DEFAULT_FACTORS = factor_exprs("thesis_core")


if __name__ == "__main__":
    run_walk_forward(DEFAULT_FACTORS)


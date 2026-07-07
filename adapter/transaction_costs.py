# -*- coding: utf-8 -*-
"""Turnover and after-cost alpha for the value-weighted decile long-short.

For each factor: build the VW top-minus-bottom decile portfolio, measure monthly
turnover, and net the long-short return of trading costs at 10/25/50 bps per unit
traded. Net FF5+UMD alpha (Newey-West) is the after-cost survival test.

Run:
  python adapter/transaction_costs.py --from-json results/llm_valid_factors.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()

import factor_lab
from adapter.sp500_loader import compute_factor
from llm_factor.config import path, sample

COST_BPS = [10, 25, 50]                 # per unit weight traded (round-trip)


def _vw_ls_weights(factor: pd.Series, me: pd.Series, q=10) -> pd.DataFrame:
    """Per (month, instrument) signed weight: +vw in top decile, -vw in bottom decile."""
    d = pd.DataFrame({"f": factor, "w": me}).replace([np.inf, -np.inf], np.nan).dropna()
    parts = []
    for t, g in d.groupby(level="datetime"):
        if len(g) < q * 2:
            continue
        b = pd.qcut(g["f"].rank(method="first"), q, labels=False)
        wt = pd.Series(0.0, index=g.index)
        for leg, sign in [(q - 1, 1.0), (0, -1.0)]:
            m = (b == leg).values
            ws = g["w"].where(pd.Series(m, index=g.index), 0.0)
            s = ws.sum()
            if s > 0:
                wt = wt + sign * ws / s
        parts.append(wt)
    return pd.concat(parts)


def turnover_and_net(expr: str, start: str) -> dict:
    fac = compute_factor(expr)
    me = factor_lab.load_me()
    label = factor_lab.load_labels()
    w = _vw_ls_weights(fac, me)
    w = w[w.index.get_level_values("datetime") >= pd.Timestamp(start)]

    # wide weight matrix (month x instrument); consecutive-month absolute change = traded
    W = w.unstack("instrument").sort_index()
    traded = W.diff().abs().sum(axis=1)                 # sum|Δp| per month (amount traded)
    oneway_turnover = 0.5 * traded                       # one-way fraction of the gross book

    # gross long-short return (weights applied to next-month return = label)
    y = label.reindex(w.index)
    gross = (w * y).groupby(level="datetime").sum().reindex(W.index).dropna()

    ann_turn = float(oneway_turnover.reindex(gross.index).mean() * 12)
    out = {"ann_oneway_turnover": ann_turn}
    a_gross = (factor_lab._alphas(gross) or {}).get("FF5+UMD") or {}
    out["gross_alpha_ann"] = a_gross.get("alpha_ann")
    out["gross_alpha_t"] = a_gross.get("alpha_t")
    for bps in COST_BPS:
        cost = (bps / 1e4) * traded.reindex(gross.index).fillna(0.0)
        net = (gross - cost).dropna()
        a = (factor_lab._alphas(net) or {}).get("FF5+UMD") or {}
        out[f"net_alpha_ann_{bps}bps"] = a.get("alpha_ann")
        out[f"net_alpha_t_{bps}bps"] = a.get("alpha_t")
    return out


def run(factors: dict, outdir=None, start=None) -> Path:
    start = start or sample("start", "1972-01-01")
    outdir = Path(outdir) if outdir else (path("results_root") / "transaction_costs")
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, expr in factors.items():
        r = {"name": name, **turnover_and_net(expr, start)}
        rows.append(r)
        print(f"-- {name:26} turn/yr={r['ann_oneway_turnover']*100:5.0f}%  "
              f"gross a_t={r['gross_alpha_t']:+.2f}  "
              f"net@25bps a_t={r['net_alpha_t_25bps']:+.2f}  net@50bps a_t={r['net_alpha_t_50bps']:+.2f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(outdir / "transaction_costs.csv", index=False)
    L = ["# After-cost alpha (value-weighted decile long-short)", "",
         "Annual one-way turnover and net FF5+UMD alpha (Newey-West t) after trading costs "
         "of 10/25/50 bps per unit traded.", "",
         "| Factor | turnover/yr | gross a (t) | net 10bps (t) | net 25bps (t) | net 50bps (t) |",
         "|---|--:|--:|--:|--:|--:|"]
    def c(a, t):
        return "--" if a != a else f"{a*100:+.1f}% ({t:+.2f})"
    for _, r in df.iterrows():
        L.append(f"| {r['name']} | {r['ann_oneway_turnover']*100:.0f}% | "
                 f"{c(r['gross_alpha_ann'], r['gross_alpha_t'])} | {c(r['net_alpha_ann_10bps'], r['net_alpha_t_10bps'])} | "
                 f"{c(r['net_alpha_ann_25bps'], r['net_alpha_t_25bps'])} | {c(r['net_alpha_ann_50bps'], r['net_alpha_t_50bps'])} |")
    (outdir / "transaction_costs.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\ntransaction-cost tables -> {outdir}")
    return outdir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--start", default=None)
    args = ap.parse_args()
    data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    facs = data["factors"] if isinstance(data, dict) else data
    run({c["name"]: c["expression"] for c in facs}, outdir=args.outdir, start=args.start)

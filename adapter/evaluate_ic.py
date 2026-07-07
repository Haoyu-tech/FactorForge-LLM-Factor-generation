# -*- coding: utf-8 -*-
"""
Monthly factor evaluation - the replacement for QuantaAlpha's qlib backtest
feedback. Given a factor expression, score it against next-month excess return.

Metrics (cross-sectional, monthly):
  IC      mean monthly Spearman rank corr(factor, fwd_ret)
  ICIR    mean(IC)/std(IC)                (information ratio of the signal)
  IC_t    Newey-style t-stat = ICIR*sqrt(n_months)
  IC>0%   fraction of months with positive IC
  LS_ret  annualised top-minus-bottom quintile return
  LS_SR   annualised Sharpe of the long-short spread
"""
from pathlib import Path

import numpy as np
import pandas as pd

from sp500_loader import compute_factor, load_labels  # noqa: E402

PER_YEAR = 12  # monthly


def _ic_series(factor: pd.Series, label: pd.Series) -> pd.Series:
    df = pd.DataFrame({"f": factor, "y": label}).dropna()
    return df.groupby(level="datetime").apply(
        lambda g: g["f"].corr(g["y"], method="spearman") if len(g) >= 5 else np.nan
    ).dropna()


def _long_short(factor: pd.Series, label: pd.Series, q: int = 5) -> pd.Series:
    df = pd.DataFrame({"f": factor, "y": label}).dropna()

    def spread(g):
        if len(g) < q * 2:
            return np.nan
        try:
            bucket = pd.qcut(g["f"].rank(method="first"), q, labels=False)
        except ValueError:
            return np.nan
        top = g["y"][bucket == q - 1].mean()
        bot = g["y"][bucket == 0].mean()
        return top - bot

    return df.groupby(level="datetime").apply(spread).dropna()


def summary(expr: str, start=None, end=None, q: int = 5) -> dict:
    factor = compute_factor(expr)
    label = load_labels()
    if start or end:
        idx = factor.index.get_level_values("datetime")
        m = np.ones(len(factor), dtype=bool)
        if start:
            m &= idx >= pd.Timestamp(start)
        if end:
            m &= idx <= pd.Timestamp(end)
        factor, label = factor[m], label.reindex(factor.index)

    ic = _ic_series(factor, label)
    ls = _long_short(factor, label, q)
    n = len(ic)
    icir = ic.mean() / ic.std() if ic.std() > 0 else np.nan

    return {
        "expr": expr,
        "n_months": n,
        "coverage": float(factor.notna().mean()),
        "IC": float(ic.mean()),
        "IC_std": float(ic.std()),
        "ICIR": float(icir),
        "ICIR_ann": float(icir * np.sqrt(PER_YEAR)) if n else np.nan,
        "IC_t": float(icir * np.sqrt(n)) if n else np.nan,
        "IC_pos%": float((ic > 0).mean() * 100),
        "LS_ret_ann": float(ls.mean() * PER_YEAR),
        "LS_SR": float(ls.mean() / ls.std() * np.sqrt(PER_YEAR)) if ls.std() > 0 else np.nan,
    }


def print_table(rows: list):
    cols = ["IC", "ICIR", "IC_t", "IC_pos%", "LS_ret_ann", "LS_SR", "n_months", "expr"]
    hdr = f"{'IC':>7} {'ICIR':>6} {'IC_t':>6} {'pos%':>5} {'LS_ann':>7} {'LS_SR':>6} {'n':>4}  expr"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['IC']:>7.4f} {r['ICIR']:>6.3f} {r['IC_t']:>6.2f} "
              f"{r['IC_pos%']:>5.0f} {r['LS_ret_ann']:>7.3f} {r['LS_SR']:>6.2f} "
              f"{r['n_months']:>4}  {r['expr']}")


if __name__ == "__main__":
    import sys
    exprs = sys.argv[1:] or ["$ret_12_1"]
    rows = [summary(e) for e in exprs]
    print_table(rows)


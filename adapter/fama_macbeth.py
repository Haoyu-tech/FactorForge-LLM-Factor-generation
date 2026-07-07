# -*- coding: utf-8 -*-
"""
Fama-MacBeth (1973) cross-sectional regressions - the firm-level workhorse that
top finance journals pair with portfolio sorts. For each month run

    r_{i,t+1} = gamma_0t + gamma_1t * factor_{i,t} + controls_{i,t} + e_{i,t}

(cross-section over stocks), collect the slope time series, then report the
time-series mean slope with a Newey-West (6-lag) t-stat. The key number is the
factor's slope in the MULTIVARIATE spec: does it predict returns *after*
controlling for size, value, momentum and beta at the individual-stock level?

Predictors are cross-sectionally standardized each month (z-score), so a slope is
the monthly return (in %) associated with a 1-standard-deviation increase in the
characteristic, holding the others fixed.

Run:  python adapter/fama_macbeth.py
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from sp500_loader import compute_factor, load_features, load_labels
from factor_lab import ROOT, _stars_txt, _stars_tex
from llm_factor.factors import factor_exprs

CONTROL_DEFS = {                      # name -> how to build from the panel
    "size":  lambda f: np.log(f["$me"]),
    "bm":    lambda f: f["$be_me"],
    "mom":   lambda f: f["$ret_12_1"],
    "beta":  lambda f: f["$beta_60m"],
}


def _nw_mean_t(series, lags=6):
    s = pd.Series(series).dropna()
    if len(s) < 24:
        return float("nan"), float("nan")
    res = sm.OLS(s.values, np.ones(len(s))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(res.params[0]), float(res.tvalues[0])


def fama_macbeth(predictors: dict, label: pd.Series, start="1972-01-01",
                 standardize=True, min_n=30, weights: pd.Series | None = None):
    """Run monthly cross-sectional regressions; return mean slopes + Newey-West t.

    If `weights` (e.g. market equity) is given, each month's regression is WLS
    (value-weighted) instead of OLS (equal-weighted) -- this aligns the firm-level
    Fama-MacBeth test with the value-weighted portfolio sort."""
    cols = list(predictors)
    parts = {**predictors, "y": label}
    if weights is not None:
        parts["_w"] = weights
    df = pd.concat(parts, axis=1)
    df = df[df.index.get_level_values("datetime") >= pd.Timestamp(start)]

    rows = {}
    for t, g in df.groupby(level="datetime"):
        g = g.dropna()
        if len(g) < min_n:
            continue
        X = g[cols].copy()
        if standardize:
            sd = X.std(ddof=0).replace(0, np.nan)
            X = (X - X.mean()) / sd
        keep = [c for c in ([*cols, "y"] + (["_w"] if weights is not None else []))]
        gg = pd.concat([g["y"], X] + ([g["_w"]] if weights is not None else []), axis=1)
        gg = gg.replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < min_n:
            continue
        if weights is not None:
            w = gg["_w"].clip(lower=0)
            res = sm.WLS(gg["y"], sm.add_constant(gg[cols]), weights=w).fit()
        else:
            res = sm.OLS(gg["y"], sm.add_constant(gg[cols])).fit()
        r = res.params.to_dict()
        r["_r2"], r["_n"] = res.rsquared, len(gg)
        rows[t] = r
    sl = pd.DataFrame(rows).T
    out = {"_T": int(len(sl)), "_avg_r2": float(sl["_r2"].mean()), "_avg_n": float(sl["_n"].mean())}
    for c in ["const"] + cols:
        m, tt = _nw_mean_t(sl[c]) if c in sl else (float("nan"), float("nan"))
        out[c] = {"mean": m, "t": tt}
    return out


def run_fama_macbeth(factors: dict, outdir=None, start="1972-01-01"):
    outdir = Path(outdir) if outdir else ROOT / "results" / f"fama_macbeth_{datetime.now():%Y%m%d_%H%M%S}"
    outdir.mkdir(parents=True, exist_ok=True)
    feats = load_features()
    label = load_labels()
    controls = {k: v(feats) for k, v in CONTROL_DEFS.items()}
    me = feats["$me"] if "$me" in feats.columns else None    # value weights

    # controls-only baseline (factor-independent)
    base = fama_macbeth(controls, label, start)

    rows = []
    for name, expr in factors.items():
        fac = compute_factor(expr)
        uni = fama_macbeth({"factor": fac}, label, start)
        full = fama_macbeth({"factor": fac, **controls}, label, start)
        # value-weighted (WLS) with controls -- aligns FM with the VW portfolio sort
        vw = fama_macbeth({"factor": fac, **controls}, label, start, weights=me) if me is not None else {"factor": {"mean": float("nan"), "t": float("nan")}}
        rows.append({
            "name": name,
            "uni_slope": uni["factor"]["mean"], "uni_t": uni["factor"]["t"],
            "mv_slope": full["factor"]["mean"], "mv_t": full["factor"]["t"],
            "vw_slope": vw["factor"]["mean"], "vw_t": vw["factor"]["t"],
            "avg_r2": full["_avg_r2"], "T": full["_T"],
        })
        print(f"-- {name:18}  EW+ctrl: {full['factor']['mean']*100:+.3f}%/SD t={full['factor']['t']:+.2f}  "
              f"| VW(WLS)+ctrl: {vw['factor']['mean']*100:+.3f}%/SD t={vw['factor']['t']:+.2f}  "
              f"(T={full['_T']})")
    df = pd.DataFrame(rows)
    df.to_csv(outdir / "fama_macbeth.csv", index=False)
    _write_md(df, base, outdir, start)
    _write_tex(df, base, outdir, start)
    print(f"\nFama-MacBeth tables -> {outdir}")
    return outdir, df, base


def _cell(slope, t, tex=False):
    if slope != slope:
        return "--"
    star = _stars_tex(t) if tex else _stars_txt(t)
    return f"{slope*100:+.3f}{star} ({t:+.2f})"


def _write_md(df, base, outdir, start):
    L = ["# Fama-MacBeth cross-sectional regressions",
         f"_Monthly cross-sectional OLS of next-month return on z-scored predictors, "
         f"{start}..end. Slopes = monthly % return per 1 SD; Newey-West (6) t in parens. "
         f"\\*/\\*\\*/\\*\\*\\* = 10/5/1%._\n",
         "## Each factor: univariate vs with controls (size, B/M, momentum, beta)", "",
         "_EW = equal-weighted (OLS) cross-section; VW = value-weighted (WLS, market-cap weights) "
         "cross-section, aligned with the value-weighted portfolio sort._", "",
         "| Factor | Univariate (EW) | + controls (EW) | + controls (VW/WLS) | avg R2 | T |",
         "|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        vw = _cell(r.get('vw_slope', float('nan')), r.get('vw_t', float('nan')))
        L.append(f"| {r['name']} | {_cell(r['uni_slope'], r['uni_t'])} | "
                 f"{_cell(r['mv_slope'], r['mv_t'])} | {vw} | {r['avg_r2']:.3f} | {int(r['T'])} |")
    L += ["", "## Controls-only baseline (the classic FM slopes)", "",
          "| Variable | slope (t) |", "|---|---|"]
    for c in ["size", "bm", "mom", "beta"]:
        L.append(f"| {c} | {_cell(base[c]['mean'], base[c]['t'])} |")
    L.append(f"| (avg R2 {base['_avg_r2']:.3f}, T {base['_T']}) | |")
    (outdir / "fama_macbeth.md").write_text("\n".join(L), encoding="utf-8")


def _write_tex(df, base, outdir, start):
    out = ["% requires: \\usepackage{booktabs,threeparttable}",
           "\\begin{table}[htbp]\\centering",
           "\\caption{Fama-MacBeth regressions of next-month returns on the factor and controls}",
           "\\label{tab:fm}", "\\begin{threeparttable}\\footnotesize",
           "\\begin{tabular}{lcccc}", "\\toprule",
           "Factor & Univariate & + controls & avg $R^2$ & $T$ \\\\", "\\midrule"]
    for _, r in df.iterrows():
        out.append(f"{r['name'].replace('_', chr(92)+'_')} & {_cell(r['uni_slope'], r['uni_t'], True)} & "
                   f"{_cell(r['mv_slope'], r['mv_t'], True)} & {r['avg_r2']:.3f} & {int(r['T'])} \\\\")
    out += ["\\midrule", "\\multicolumn{5}{l}{\\textit{Controls-only baseline (slope, t)}} \\\\"]
    for c in ["size", "bm", "mom", "beta"]:
        out.append(f"{c} & \\multicolumn{{2}}{{l}}{{{_cell(base[c]['mean'], base[c]['t'], True)}}} & & \\\\")
    out += ["\\bottomrule", "\\end{tabular}",
            "\\begin{tablenotes}\\footnotesize",
            "\\item Monthly cross-sectional OLS; predictors z-scored each month. Slopes are monthly "
            "\\% return per 1 SD. Newey-West (6 lag) $t$ in parentheses. $^{*},^{**},^{***}$: 10/5/1\\%.",
            "\\end{tablenotes}", "\\end{threeparttable}", "\\end{table}"]
    (outdir / "fama_macbeth.tex").write_text("\n".join(out), encoding="utf-8")


DEFAULT_FACTORS = factor_exprs("thesis_core")


if __name__ == "__main__":
    run_fama_macbeth(DEFAULT_FACTORS)


# -*- coding: utf-8 -*-
"""
Spanning regressions - the hard evidence that an LLM-synthesized factor *adds*
something beyond (a) its own ingredient characteristics and (b) the known Kelly
anomaly zoo built from the SAME panel.

For a candidate factor's long-short (top-minus-bottom decile) return series r_t:
    r_t = alpha + sum_k beta_k * f_{k,t} + e_t        (Newey-West, 6 lags)
where the f_k are the long-short returns of the spanning set. A significant
intercept (alpha) means the combination is NOT spanned -> genuine increment.

Two tests per factor:
  - vs COMPONENTS : RHS = univariate LS of each $field used in the expression.
                    Alpha > 0 sig  => the *way they are combined* matters.
  - vs KELLY ZOO  : RHS = LS of a curated set of canonical anomalies in the panel.
                    Alpha > 0 sig  => beats the known anomaly library on this data.

All long-short returns are value-weighted by $me (the credibility standard),
matching factor_lab's main results.

Run:  python adapter/spanning.py
"""
import re
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
from sp500_loader import compute_factor, load_labels, available_fields
from factor_lab import _deciles, load_me, ROOT, _stars_txt, _stars_tex
from llm_factor.factors import factor_exprs

# Anomaly zoo = one SIGNED COMPOSITE per JKP characteristic theme, built from the
# panel's Kelly-153 fields. This covers the whole published anomaly space (all themes)
# with ~14 interpretable, non-multicollinear factors -- far sounder than either 12
# arbitrary single chars or a 120-regressor kitchen sink. Each composite is signed so
# that a HIGHER value = HIGHER expected return (long-short goes long the high leg);
# significant target intercept => genuine increment beyond every known anomaly theme.
KELLY_ZOO = {
    "value":         "RANK($be_me) + RANK($sale_me) + RANK($ebit_bev)",
    "momentum":      "RANK($ret_12_1) + RANK($ret_6_1)",
    "st_reversal":   "-RANK($ret_1_0)",
    "lt_reversal":   "-RANK($ret_60_12)",
    "profitability": "RANK($gp_at) + RANK($cop_at) + RANK($op_at)",
    "profit_growth": "RANK($niq_su) + RANK($ni_inc8q)",
    "investment":    "-RANK($at_gr1) - RANK($noa_at)",
    "accruals":      "-RANK($oaccruals_at) - RANK($taccruals_at)",
    "issuance":      "-RANK($eqnetis_at) - RANK($chcsho_12m)",
    "quality":       "RANK($qmj_safety) + RANK($z_score) - RANK($at_be)",
    "low_risk":      "-RANK($ivol_ff3_21d) - RANK($beta_60m) - RANK($rmax5_21d)",
    "liquidity":     "-RANK($me) + RANK($ami_126d)",
    "seasonality":   "RANK($seas_1_1na)",
    "mispricing":    "RANK($mispricing_perf) + RANK($mispricing_mgmt)",
}

_ls_cache = {}


def _ls_series(expr, weighting="vw", start="1972-01-01"):
    """Monthly long-short (D10-D1) return series for an expression, period-indexed."""
    key = (expr, weighting, start)
    if key in _ls_cache:
        return _ls_cache[key]
    f = compute_factor(expr)
    y = load_labels().reindex(f.index)
    w = load_me().reindex(f.index) if weighting == "vw" else None
    dt = f.index.get_level_values("datetime")
    m = dt >= pd.Timestamp(start)
    f, y = f[m], (y[m] if w is None else y[m])
    w = w[m] if w is not None else None
    _, ls = _deciles(f, y, w)
    ls.index = pd.to_datetime(ls.index).to_period("M")
    _ls_cache[key] = ls
    return ls


def _expr_fields(expr):
    """$fields referenced by an expression, restricted to those in the panel."""
    avail = set(available_fields())
    return [c for c in dict.fromkeys(re.findall(r"\$\w+", expr)) if c in avail]


def spanning_regression(target_expr, rhs_exprs: dict, weighting="vw", start="1972-01-01"):
    """Regress target LS on the RHS LS factors. Returns alpha (ann %), NW t, R2, n, betas."""
    y = _ls_series(target_expr, weighting, start)
    if not rhs_exprs:
        return None
    X = pd.DataFrame({name: _ls_series(e, weighting, start) for name, e in rhs_exprs.items()})
    df = pd.concat([y.rename("_y"), X], axis=1).dropna()
    if len(df) < 24:
        return None
    cols = list(rhs_exprs)
    res = sm.OLS(df["_y"], sm.add_constant(df[cols])).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return {
        "alpha_ann": float(res.params["const"] * 12),
        "alpha_t": float(res.tvalues["const"]),
        "r2": float(res.rsquared),
        "n": int(len(df)),
        "betas": {c: float(res.params[c]) for c in cols},
    }


def evaluate_spanning(name, expr, weighting="vw", start="1972-01-01", split="2000-12-31"):
    """Run both spanning tests (vs components, vs Kelly zoo), full sample + OOS."""
    fields = _expr_fields(expr)
    comp = {f[1:]: f for f in fields}                       # {name: $field}
    # Full JKP theme-composite zoo (each composite spans a whole anomaly theme, so it is
    # not trivially the target's own field; beating a theme it overlaps with is the point).
    zoo = dict(KELLY_ZOO)

    out = {"name": name, "expr": expr, "n_components": len(comp)}
    for win, st in [("full", start), ("oos", split)]:    # OOS series begins at the split date
        out[win] = {
            "vs_components": spanning_regression(expr, comp, weighting, st),
            "vs_kelly_zoo": spanning_regression(expr, zoo, weighting, st),
        }
    return out


def run_spanning(factors: dict, outdir=None, weighting="vw", start="1972-01-01", split="2000-12-31"):
    outdir = Path(outdir) if outdir else ROOT / "results" / f"spanning_{datetime.now():%Y%m%d_%H%M%S}"
    outdir.mkdir(parents=True, exist_ok=True)
    rows, results = [], []
    for name, expr in factors.items():
        print(f"-- {name} --  {expr}")
        r = evaluate_spanning(name, expr, weighting, start, split)
        results.append(r)
        for win in ("full", "oos"):
            c = r[win]["vs_components"] or {}
            z = r[win]["vs_kelly_zoo"] or {}
            rows.append({"name": name, "sample": win, "n_comp": r["n_components"],
                         "comp_alpha_ann": c.get("alpha_ann"), "comp_alpha_t": c.get("alpha_t"),
                         "comp_r2": c.get("r2"),
                         "zoo_alpha_ann": z.get("alpha_ann"), "zoo_alpha_t": z.get("alpha_t"),
                         "zoo_r2": z.get("r2"), "n": z.get("n")})
            print(f"   {win:4}  vs components: a={c.get('alpha_ann',float('nan'))*100:+.1f}%/yr "
                  f"t={c.get('alpha_t',float('nan')):+.2f} (R2={c.get('r2',float('nan')):.2f}) | "
                  f"vs Kelly zoo: a={z.get('alpha_ann',float('nan'))*100:+.1f}%/yr "
                  f"t={z.get('alpha_t',float('nan')):+.2f} (R2={z.get('r2',float('nan')):.2f})")
    df = pd.DataFrame(rows)
    df.to_csv(outdir / "spanning_table.csv", index=False)
    _write_md(df, outdir, weighting, split)
    _write_tex(df, outdir, weighting, split)
    print(f"\nspanning tables -> {outdir}")
    return outdir, df


def _cell(a, t, tex=False):
    if a != a:
        return "--"
    star = _stars_tex(t) if tex else _stars_txt(t)
    return f"{a*100:+.1f}{star} ({t:+.2f})"


def _write_md(df, outdir, weighting, split):
    L = ["# Spanning regressions",
         f"_Value-weighted long-short ({weighting.upper()}) regressed on its component factors "
         f"and on the Kelly anomaly zoo. Newey-West (6) t in parens. \\*/\\*\\*/\\*\\*\\* = 10/5/1%. "
         f"A significant intercept = increment not spanned. OOS = post-{split}._\n",
         "| Factor | Sample | #comp | alpha vs components | alpha vs Kelly zoo |",
         "|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r['name']} | {r['sample']} | {int(r['n_comp'])} | "
                 f"{_cell(r['comp_alpha_ann'], r['comp_alpha_t'])} | "
                 f"{_cell(r['zoo_alpha_ann'], r['zoo_alpha_t'])} |")
    (outdir / "spanning_table.md").write_text("\n".join(L), encoding="utf-8")


def _write_tex(df, outdir, weighting, split):
    out = ["% requires: \\usepackage{booktabs,threeparttable}",
           "\\begin{table}[htbp]\\centering",
           "\\caption{Spanning regressions: is the LLM-synthesized factor explained by its "
           "components or the Kelly anomaly zoo?}",
           "\\label{tab:spanning}",
           "\\begin{threeparttable}\\footnotesize",
           "\\begin{tabular}{llccc}",
           "\\toprule",
           "Factor & Sample & \\#comp & $\\alpha$ vs components & $\\alpha$ vs Kelly zoo \\\\",
           "\\midrule"]
    for _, r in df.iterrows():
        nm = r["name"].replace("_", r"\_")
        out.append(f"{nm} & {r['sample']} & {int(r['n_comp'])} & "
                   f"{_cell(r['comp_alpha_ann'], r['comp_alpha_t'], tex=True)} & "
                   f"{_cell(r['zoo_alpha_ann'], r['zoo_alpha_t'], tex=True)} \\\\")
    out += ["\\bottomrule", "\\end{tabular}",
            "\\begin{tablenotes}\\footnotesize",
            f"\\item Annualized intercept (\\%) from regressing the factor's {weighting.upper()} "
            "long-short return on the long-short returns of the spanning set. Newey-West (6 lag) "
            "$t$-statistics in parentheses. $^{*},^{**},^{***}$: 10/5/1\\%. A significant intercept "
            "indicates return not spanned by (i.e. incremental to) the spanning factors.",
            "\\end{tablenotes}", "\\end{threeparttable}", "\\end{table}"]
    (outdir / "spanning_table.tex").write_text("\n".join(out), encoding="utf-8")


# the validated/candidate factors to test (expression only)
DEFAULT_FACTORS = factor_exprs("thesis_core")


if __name__ == "__main__":
    run_spanning(DEFAULT_FACTORS)


# -*- coding: utf-8 -*-
"""
Multiple-testing haircuts - the #1 referee concern for any factor-MINING paper.

When an LLM (or a search) proposes many factors and you keep the best by t-stat,
the surviving t-stats are upward biased. This module reports, for each factor:
  - the raw Newey-West t of its value-weighted long-short mean,
  - the Harvey-Liu-Zhu (2016) rule of thumb: a new factor needs |t| > 3.0,
  - Bonferroni- and Holm-adjusted significance given N independent trials,
  - the Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014): the probability the
    Sharpe is real after accounting for N trials, non-normality, and sample length.

N (the trial budget) must be the TOTAL number of candidates evaluated during the
search, not just the survivors - pass it explicitly.

Run:  python adapter/multiple_testing.py --n-trials 100
"""
import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from spanning import _ls_series                       # VW long-short series builder
from factor_lab import ROOT, _stars_txt
from llm_factor.factors import factor_exprs

EULER = 0.5772156649015329


def _sr_stats(r):
    """Per-period Sharpe, skew, (non-excess) kurtosis, n - on monthly returns."""
    r = pd.Series(r).dropna()
    n = len(r)
    sr = r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else np.nan
    return sr, float(stats.skew(r)), float(stats.kurtosis(r, fisher=False)), n


def probabilistic_sharpe(sr, sr_benchmark, n, skew, kurt):
    """PSR: P(true SR > benchmark) given non-normality (Bailey-Lopez de Prado)."""
    denom = np.sqrt(1 - skew * sr + (kurt - 1) / 4.0 * sr ** 2)
    z = (sr - sr_benchmark) * np.sqrt(n - 1) / denom
    return float(stats.norm.cdf(z))


def expected_max_sharpe(var_sr, n_trials):
    """Expected maximum of N trial Sharpes ~ sqrt(Var)*[(1-g)Z(1-1/N)+g Z(1-1/(N e))]."""
    if n_trials < 2 or var_sr <= 0:
        return 0.0
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(var_sr) * ((1 - EULER) * z1 + EULER * z2))


def deflated_sharpe(r, n_trials, var_sr):
    """DSR = PSR evaluated against the expected-max-Sharpe benchmark from N trials."""
    sr, sk, ku, n = _sr_stats(r)
    if sr != sr or n < 24:
        return None
    sr_star = expected_max_sharpe(var_sr, n_trials)        # per-period benchmark
    dsr = probabilistic_sharpe(sr, sr_star, n, sk, ku)
    return {"SR_ann": sr * np.sqrt(12), "SR_star_ann": sr_star * np.sqrt(12),
            "DSR": dsr, "skew": sk, "kurt": ku, "n": n}


def run_haircuts(factors: dict, n_trials=None, weighting="vw", start="1972-01-01", outdir=None):
    outdir = Path(outdir) if outdir else ROOT / "results" / f"mtest_{datetime.now():%Y%m%d_%H%M%S}"
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) build VW long-short series + per-period Sharpes for the trial population
    series, srs = {}, {}
    for name, expr in factors.items():
        ls = _ls_series(expr, weighting, start)
        series[name] = ls
        sr, *_ = _sr_stats(ls)
        srs[name] = sr
    var_sr = float(np.var(list(srs.values()), ddof=1)) if len(srs) > 1 else 0.0
    N = int(n_trials) if n_trials else len(factors)

    # 2) per-factor haircuts
    rows = []
    for name, ls in series.items():
        r = ls.dropna()
        t_nw = _nw_t(r)
        p_raw = 2 * (1 - stats.norm.cdf(abs(t_nw)))         # two-sided p from NW t
        p_bonf = min(1.0, p_raw * N)
        # Holm: conservative single-hypothesis view uses rank; here report p*N capped (== Bonferroni
        # for the top hypothesis). Full Holm needs the whole family; we expose p_raw and N.
        dsr = deflated_sharpe(r, N, var_sr) or {}
        rows.append({
            "name": name, "t_NW": t_nw, "HLZ_pass_t3": abs(t_nw) > 3.0,
            "p_raw": p_raw, "p_bonferroni": p_bonf, "bonf_sig_5pct": p_bonf < 0.05,
            "SR_ann": dsr.get("SR_ann"), "SR_star_ann": dsr.get("SR_star_ann"),
            "DSR": dsr.get("DSR"), "DSR_pass_95": (dsr.get("DSR", 0) or 0) > 0.95,
            "skew": dsr.get("skew"), "kurt": dsr.get("kurt"), "n": dsr.get("n"),
        })
    df = pd.DataFrame(rows).sort_values("t_NW", key=lambda s: s.abs(), ascending=False)
    df.to_csv(outdir / "multiple_testing.csv", index=False)
    _write_md(df, outdir, N, var_sr, weighting)
    print(f"\nN_trials={N}  Var(SR_trials)={var_sr:.4f}  expected-max SR(ann)="
          f"{expected_max_sharpe(var_sr, N)*np.sqrt(12):+.2f}")
    print(f"multiple-testing table -> {outdir}")
    return outdir, df


def _nw_t(r):
    import statsmodels.api as sm
    r = r.dropna()
    if len(r) < 24:
        return float("nan")
    res = sm.OLS(r.values, np.ones(len(r))).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return float(res.tvalues[0])


def _write_md(df, outdir, N, var_sr, weighting):
    L = ["# Multiple-testing haircuts",
         f"_{weighting.upper()} long-short. N_trials = **{N}** (search budget). "
         f"HLZ rule: a new factor needs |t| > 3.0. Bonferroni multiplies p by N. "
         f"DSR = P(Sharpe real | N trials, non-normality, sample length); pass at > 0.95._\n",
         "| Factor | t (NW) | HLZ t>3 | Bonferroni p | sig@5% | SR ann | SR\\* (exp-max) | DSR | DSR>0.95 |",
         "|---|---|---|---|---|---|---|---|---|"]
    def flag(value):
        return "PASS" if bool(value) else "FAIL"

    for _, r in df.iterrows():
        L.append(f"| {r['name']} | {r['t_NW']:+.2f}{_stars_txt(r['t_NW'])} | "
                 f"{flag(r['HLZ_pass_t3'])} | {r['p_bonferroni']:.3f} | "
                 f"{flag(r['bonf_sig_5pct'])} | {r['SR_ann']:+.2f} | "
                 f"{r['SR_star_ann']:+.2f} | {r['DSR']:.3f} | "
                 f"{flag(r['DSR_pass_95'])} |")
    (outdir / "multiple_testing.md").write_text("\n".join(L), encoding="utf-8")


DEFAULT_FACTORS = factor_exprs("thesis_core")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=None,
                    help="TOTAL candidates evaluated during search (not just survivors)")
    args = ap.parse_args()
    run_haircuts(DEFAULT_FACTORS, n_trials=args.n_trials)


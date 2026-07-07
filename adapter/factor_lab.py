# -*- coding: utf-8 -*-
"""
Factor evaluation lab - the rigorous gate for mined factors (asset-pricing grade).

For each factor (which MUST come with an economic rationale) it computes, on the
S&P 500 monthly panel, full-sample + out-of-sample (train/test split), and under
BOTH equal-weighted (EW) and value-weighted (VW, by $me) long-short portfolios:
  - RankIC / ICIR / IC_t  (weighting-free, rank-based)
  - decile portfolios + monotonicity (Spearman of decile vs mean return)
  - long-short (D10-D1) return, annualised, Sharpe, Newey-West t-stat of the mean
  - a LADDER of factor-model alphas (Newey-West t): CAPM, FF3, Carhart4, FF5, FF5+UMD
  - a PASS/FAIL verdict (rationale present, VW FF5+UMD alpha sig full+OOS, monotone, IC OOS same sign)
and renders a 4-panel figure. Also emits publication-grade alpha tables
(academic_table_{vw,ew}.tex + academic_table.{md,csv}) with full-sample and OOS panels.

Value-weighting note: VW is the investable / credibility standard for large caps;
EW is reported alongside (anomalies typically shrink under VW). Weights = $me at the
formation month (contemporaneous with the factor, before the forward return).

Run:  python adapter/factor_lab.py          # evaluates a default factor set
"""
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from sp500_loader import compute_factor, load_labels, load_features
from llm_factor.config import evaluation, path
from llm_factor.factors import factor_tuples

ROOT = Path(__file__).resolve().parents[1]
# FF5 + momentum monthly (cols: mktrf smb hml rmw cma rf umd dateff). One file
# serves every nested benchmark from CAPM up to FF5+UMD (fixes the old bug where
# the "3 Factors Plus Momentum" file was loaded but UMD was dropped).
FF = path("fama_french_ff5_momentum")

# nested factor-model ladder (academic standard)
MODELS = {
    "CAPM":     ["mktrf"],
    "FF3":      ["mktrf", "smb", "hml"],
    "Carhart4": ["mktrf", "smb", "hml", "umd"],
    "FF5":      ["mktrf", "smb", "hml", "rmw", "cma"],
    "FF5+UMD":  ["mktrf", "smb", "hml", "rmw", "cma", "umd"],
}
PRIMARY_MODEL = evaluation("primary_model", "FF5+UMD")   # strongest benchmark = the honesty test for "real" alpha

_ff_cache = None
_me_cache = None


def load_factors() -> pd.DataFrame:
    """Monthly FF5 + UMD factor returns (decimal), indexed by month period."""
    global _ff_cache
    if _ff_cache is None:
        import zipfile
        z = zipfile.ZipFile(FF)
        with z.open(z.namelist()[0]) as fh:
            df = pd.read_csv(fh)
        df["ym"] = pd.to_datetime(df["dateff"]).dt.to_period("M")
        _ff_cache = df.set_index("ym")[["mktrf", "smb", "hml", "rmw", "cma", "umd"]]
    return _ff_cache


def load_me() -> pd.Series:
    """Market equity ($me) for value-weighting; None if absent from the panel."""
    global _me_cache
    if _me_cache is None:
        feats = load_features()
        _me_cache = feats["$me"] if "$me" in feats.columns else None
    return _me_cache


def _ic_series(factor, label):
    d = pd.DataFrame({"f": factor, "y": label}).dropna()
    return d.groupby(level="datetime").apply(
        lambda g: g["f"].corr(g["y"], method="spearman") if len(g) >= 10 else np.nan).dropna()


def _deciles(factor, label, weights=None, q=10):
    """Decile portfolios. weights=None -> equal-weight; else value-weight within bucket."""
    data = {"f": factor, "y": label}
    if weights is not None:
        data["w"] = weights
    d = pd.DataFrame(data).dropna()

    def bucket(g):
        if len(g) < q * 2:
            return None
        b = pd.qcut(g["f"].rank(method="first"), q, labels=False)
        if weights is None:
            return g["y"].groupby(b).mean()
        return g.groupby(b).apply(
            lambda x: np.average(x["y"], weights=x["w"]) if x["w"].sum() > 0 else np.nan)

    rows = {t: bucket(g) for t, g in d.groupby(level="datetime")}
    rows = {t: r for t, r in rows.items() if r is not None}
    dec = pd.DataFrame(rows).T                       # index=month, cols=0..q-1
    ls = (dec[q - 1] - dec[0]).dropna()              # monthly long-short
    return dec, ls


def _ls_mean_t(ls):
    """Newey-West t-stat of the long-short mean (HAC, 6 lags)."""
    y = ls.dropna()
    if len(y) < 24:
        return float("nan")
    res = sm.OLS(y.values, np.ones(len(y))).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return float(res.tvalues[0])


def _alphas(ls):
    """Regress the long-short series on every benchmark model (Newey-West, 6 lags).

    Returns {model_name: {alpha_m, alpha_ann, alpha_t, betas{...}, n}} (or None per model).
    """
    ff = load_factors()
    y = ls.copy()
    y.index = y.index.get_level_values("datetime") if isinstance(y.index, pd.MultiIndex) else y.index
    y.index = pd.to_datetime(y.index).to_period("M")
    out = {}
    for name, cols in MODELS.items():
        d = pd.concat([y.rename("ls"), ff[cols]], axis=1).dropna()
        if len(d) < 24:
            out[name] = None
            continue
        X = sm.add_constant(d[cols])
        res = sm.OLS(d["ls"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
        out[name] = {
            "alpha_m": float(res.params["const"]),
            "alpha_ann": float(res.params["const"] * 12),
            "alpha_t": float(res.tvalues["const"]),
            "betas": {c: float(res.params[c]) for c in cols},
            "n": int(len(d)),
        }
    return out


def _ls_block(ls):
    return {
        "LS_ann": float(ls.mean() * 12),
        "LS_SR": float(ls.mean() / ls.std() * np.sqrt(12)) if ls.std() > 0 else np.nan,
        "LS_t": _ls_mean_t(ls),
        "alphas": _alphas(ls),
    }


def _window_stats(factor, label, weights, mask):
    f, y = factor[mask], label[mask]
    w = weights[mask] if weights is not None else None
    ic = _ic_series(f, y)
    icir = ic.mean() / ic.std() if ic.std() > 0 else np.nan

    dec_ew, ls_ew = _deciles(f, y, None)
    mono = float(pd.Series(range(dec_ew.shape[1])).corr(dec_ew.mean().reset_index(drop=True), method="spearman"))
    stats = {
        "IC": float(ic.mean()), "ICIR": float(icir),
        "IC_t": float(icir * np.sqrt(len(ic))) if len(ic) else np.nan,
        "n_months": int(len(ic)), "mono": mono,
        "ew": _ls_block(ls_ew),
    }
    if w is not None:
        dec_vw, ls_vw = _deciles(f, y, w)
        stats["mono_vw"] = float(pd.Series(range(dec_vw.shape[1])).corr(dec_vw.mean().reset_index(drop=True), method="spearman"))
        stats["vw"] = _ls_block(ls_vw)
    else:
        ls_vw = ls_ew
        stats["mono_vw"] = mono
        stats["vw"] = stats["ew"]
    return stats, dec_ew, ls_ew, ls_vw, ic


def evaluate_factor_full(name, expr, rationale, start="1972-01-01", split="2000-12-31"):
    if not rationale or not rationale.strip():
        raise ValueError(f"factor '{name}' has no economic rationale (required)")
    factor = compute_factor(expr)
    label = load_labels().reindex(factor.index)
    weights = load_me()
    if weights is not None:
        weights = weights.reindex(factor.index)
    dt = factor.index.get_level_values("datetime")
    base = dt >= pd.Timestamp(start)
    full, train, test = base, base & (dt <= pd.Timestamp(split)), base & (dt > pd.Timestamp(split))

    res = {"name": name, "expr": expr, "rationale": rationale, "split": split}
    res["full"], dec_f, ls_ew_f, ls_vw_f, ic_f = _window_stats(factor, label, weights, full)
    res["train"], *_ = _window_stats(factor, label, weights, train)
    res["test"], *_ = _window_stats(factor, label, weights, test)

    # Verdict: value-weighted alpha must survive the strongest benchmark (FF5+UMD), full and OOS.
    af = (res["full"]["vw"].get("alphas") or {}).get(PRIMARY_MODEL)
    at = (res["test"]["vw"].get("alphas") or {}).get(PRIMARY_MODEL)
    checks = {
        "econ_rationale": bool(rationale.strip()),
        f"VW_{PRIMARY_MODEL}_alpha_sig_full": bool(af and abs(af["alpha_t"]) > evaluation("pass_alpha_t", 1.96)),
        f"VW_{PRIMARY_MODEL}_alpha_sig_oos": bool(at and abs(at["alpha_t"]) > evaluation("pass_alpha_t", 1.96)),
        "monotone_full": abs(res["full"]["mono"]) >= 0.8,
        "oos_ic_same_sign": np.sign(res["train"]["IC"]) == np.sign(res["test"]["IC"]) and res["test"]["IC"] != 0,
    }
    res["checks"] = checks
    res["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    res["_plot"] = (dec_f, ls_ew_f, ls_vw_f, ic_f, split)
    return res


def plot_factor(res, outdir: Path):
    dec_f, ls_ew, ls_vw, ic_f, split = res.pop("_plot")
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    # escape '$' so matplotlib does not treat "$field_a$field_b" as mathtext (double subscript)
    fig.suptitle(f"{res['name']}   [{res['verdict']}]   {res['expr']}".replace("$", r"\$"),
                 fontsize=11, fontweight="bold")

    # (0,0) decile monotonicity (equal-weight)
    dm = dec_f.mean() * 12 * 100
    colors = ["#2c7fb8" if v >= 0 else "#d95f0e" for v in dm.values]
    ax[0, 0].bar(range(len(dm)), dm.values, color=colors)
    ax[0, 0].set_title(f"Decile mean return EW (ann %)  | monotonicity corr={res['full']['mono']:.2f}")
    ax[0, 0].set_xlabel("decile (low-to-high factor)"); ax[0, 0].axhline(0, color="k", lw=.5)

    # (0,1) cumulative long-short: EW vs VW
    def _cs(ls):
        idx = pd.to_datetime(ls.index.get_level_values("datetime")) if isinstance(ls.index, pd.MultiIndex) else pd.to_datetime(ls.index)
        return pd.Series(ls.values.cumsum(), index=idx)
    e, v = _cs(ls_ew), _cs(ls_vw)
    ax[0, 1].plot(e.index, e.values * 100, color="#1a9850", label="equal-weight")
    ax[0, 1].plot(v.index, v.values * 100, color="#d95f0e", label="value-weight")
    ax[0, 1].axvline(pd.Timestamp(split), color="gray", ls="--")
    ax[0, 1].legend(fontsize=8, loc="upper left")
    ax[0, 1].set_title("Cumulative long-short return (%): EW vs VW  | split=train|test")

    # (1,0) cumulative IC
    ici = pd.to_datetime(ic_f.index)
    ax[1, 0].plot(ici, ic_f.values.cumsum(), color="#756bb1")
    ax[1, 0].axvline(pd.Timestamp(split), color="gray", ls="--")
    ax[1, 0].set_title("Cumulative monthly RankIC")

    # (1,1) text panel
    def fmt(w):
        s = res[w]; vw = s.get("vw") or {}; ew = s.get("ew") or {}
        a6v = (vw.get("alphas") or {}).get("FF5+UMD") or {}
        a6e = (ew.get("alphas") or {}).get("FF5+UMD") or {}
        return (f"{w:5} IC={s['IC']:+.4f} t={s['IC_t']:+.2f}  mono(EW)={s['mono']:+.2f}\n"
                f"   VW: LS={vw.get('LS_ann',float('nan'))*100:+.1f}% SR={vw.get('LS_SR',float('nan')):+.2f}  "
                f"FF5+UMD alpha={a6v.get('alpha_ann',float('nan'))*100:+.1f}%/yr t={a6v.get('alpha_t',float('nan')):+.2f}\n"
                f"   EW: LS={ew.get('LS_ann',float('nan'))*100:+.1f}% SR={ew.get('LS_SR',float('nan')):+.2f}  "
                f"FF5+UMD alpha={a6e.get('alpha_ann',float('nan'))*100:+.1f}%/yr t={a6e.get('alpha_t',float('nan')):+.2f}")
    import textwrap
    rat = "\n".join(textwrap.wrap(res["rationale"], width=62))
    txt = (f"ECON RATIONALE:\n{rat}\n\n" + fmt("full") + "\n" + fmt("train") + "\n" + fmt("test")
           + "\n\nVERDICT: " + res["verdict"] + "\n"
           + "\n".join(f"  [{'x' if v else ' '}] {k}" for k, v in res["checks"].items()))
    ax[1, 1].axis("off"); ax[1, 1].text(0, 1, txt.replace("$", r"\$"), va="top", ha="left", family="monospace", fontsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(outdir / f"{res['name']}.png", dpi=110); plt.close(fig)


# ----------------------------------------------------------------- academic table
def _stars_tex(t):
    if t != t:
        return ""
    a = abs(t)
    return "$^{***}$" if a > 2.576 else "$^{**}$" if a > 1.96 else "$^{*}$" if a > 1.645 else ""


def _stars_txt(t):
    if t != t:
        return ""
    a = abs(t)
    return "***" if a > 2.576 else "**" if a > 1.96 else "*" if a > 1.645 else ""


def _flat_row(res, sample, wt):
    s = res[sample]; blk = s.get(wt) or {}; al = blk.get("alphas") or {}
    row = {"name": res["name"], "sample": sample, "weight": wt, "expr": res["expr"],
           "IC_t": s["IC_t"], "mono": s["mono"],
           "LS_ann": blk.get("LS_ann", float("nan")), "LS_t": blk.get("LS_t", float("nan")),
           "LS_SR": blk.get("LS_SR", float("nan"))}
    for m in MODELS:
        a = al.get(m) or {}
        row[f"{m}_alpha_ann"] = a.get("alpha_ann", float("nan"))
        row[f"{m}_alpha_t"] = a.get("alpha_t", float("nan"))
    return row


def academic_table(all_res, outdir, split="2000-12-31"):
    """Publication-grade alpha tables: VW (main) + EW (appendix) LaTeX, plus md/csv.

    Each weighting -> two panels (full / out-of-sample). Columns = the factor-model
    ladder; Newey-West t-stats in parentheses; significance stars at 10/5/1%.
    """
    mods = list(MODELS)
    df = pd.DataFrame([_flat_row(r, s, w) for r in all_res
                       for s in ("full", "test") for w in ("vw", "ew")])
    df.to_csv(outdir / "academic_table.csv", index=False)

    # ---- markdown (all four panels) ----
    head = "| Factor | LS ann% (t) | " + " | ".join(f"{m} alpha (t)" for m in mods) + " | IC_t | mono |"
    sep = "|" + "---|" * (len(mods) + 4)

    def md_rows(sample, wt):
        d = df[(df["sample"] == sample) & (df["weight"] == wt)]
        L = []
        for _, r in d.iterrows():
            cells = [f"{r[f'{m}_alpha_ann']*100:+.1f}{_stars_txt(r[f'{m}_alpha_t'])} ({r[f'{m}_alpha_t']:+.2f})" for m in mods]
            ls = f"{r['LS_ann']*100:+.1f} ({r['LS_t']:+.2f})"
            L.append(f"| {r['name']} | {ls} | " + " | ".join(cells) + f" | {r['IC_t']:+.2f} | {r['mono']:+.2f} |")
        return L

    md = ["# Risk-adjusted performance of mined factors",
          f"_Long-short = top-minus-bottom decile, monthly rebalanced. Newey-West (6 lag) "
          f"t-stats in parentheses. \\*/\\*\\*/\\*\\*\\* = 10/5/1%. OOS = post-{split}. "
          f"IC_t and mono are equal-weight / rank-based (weighting-free)._\n"]
    for wt, wlab in [("vw", "Value-weighted (main)"), ("ew", "Equal-weighted")]:
        for sample, slab in [("full", "Full sample"), ("test", f"Out-of-sample (post-{split})")]:
            md += [f"## {wlab} - {slab}", "", head, sep] + md_rows(sample, wt) + [""]
    (outdir / "academic_table.md").write_text("\n".join(md), encoding="utf-8")

    # ---- LaTeX (one file per weighting; two physical rows per factor: alpha then t) ----
    align = "l" + "c" * (len(mods) + 1)

    def tex_panel(sample, title, wt):
        d = df[(df["sample"] == sample) & (df["weight"] == wt)]
        out = [f"\\multicolumn{{{len(mods)+2}}}{{l}}{{\\textit{{{title}}}}} \\\\", "\\addlinespace"]
        for _, r in d.iterrows():
            nm = r["name"].replace("_", r"\_")
            a = " & ".join(f"{r[f'{m}_alpha_ann']*100:+.1f}{_stars_tex(r[f'{m}_alpha_t'])}" for m in mods)
            t = " & ".join(f"({r[f'{m}_alpha_t']:+.2f})" for m in mods)
            out.append(f"{nm} & {r['LS_ann']*100:+.1f} & {a} \\\\")
            out.append(f" & ({r['LS_t']:+.2f}) & {t} \\\\")
            out.append("\\addlinespace")
        return "\n".join(out)

    for wt, wlab, fn in [("vw", "value-weighted", "academic_table_vw.tex"),
                         ("ew", "equal-weighted", "academic_table_ew.tex")]:
        tex = [
            "% requires: \\usepackage{booktabs,threeparttable}",
            "\\begin{table}[htbp]\\centering",
            f"\\caption{{Risk-adjusted performance of LLM-mined factors ({wlab} long-short)}}",
            f"\\label{{tab:alphas_{wt}}}",
            "\\begin{threeparttable}\\footnotesize",
            f"\\begin{{tabular}}{{{align}}}",
            "\\toprule",
            f" & Mean LS & \\multicolumn{{{len(mods)}}}{{c}}{{Annualized alpha (\\%)}} \\\\",
            f"\\cmidrule(lr){{3-{len(mods)+2}}}",
            "Factor & (ann \\%) & " + " & ".join(mods) + " \\\\",
            "\\midrule",
            tex_panel("full", "Panel A: Full sample", wt),
            "\\midrule",
            tex_panel("test", f"Panel B: Out-of-sample (post-{split})", wt),
            "\\bottomrule",
            "\\end{tabular}",
            "\\begin{tablenotes}\\footnotesize",
            f"\\item Long-short = top-minus-bottom decile ({wlab}), monthly rebalanced. "
            "Newey-West (6 lag) $t$-statistics in parentheses. "
            "$^{*}$, $^{**}$, $^{***}$ denote significance at the 10\\%, 5\\%, 1\\% levels.",
            "\\end{tablenotes}",
            "\\end{threeparttable}",
            "\\end{table}",
        ]
        (outdir / fn).write_text("\n".join(tex), encoding="utf-8")
    print(f"academic tables -> {outdir/'academic_table_vw.tex'} / _ew.tex (+ .md/.csv)")
    return df


RATIONALE_JSON = ROOT / "results" / "factor_rationales.json"
RATIONALE_MD = ROOT / "results" / "factor_rationales.md"


def update_rationale_library(results):
    """Persist the economic/financial explanation of each factor (dedup by expression).

    PASS factors = economically grounded AND empirically validated (VALUE-WEIGHTED
    FF5+UMD alpha significant full+OOS, monotone decile).
    """
    RATIONALE_JSON.parent.mkdir(parents=True, exist_ok=True)
    store = json.loads(RATIONALE_JSON.read_text(encoding="utf-8")) if RATIONALE_JSON.exists() else {}
    for res in results:
        rat = (res.get("rationale") or "").strip()
        if not rat:
            continue
        avw = (res["full"]["vw"].get("alphas") or {})
        atvw = (res["test"]["vw"].get("alphas") or {})
        a3 = avw.get("FF3") or {}
        a6 = avw.get("FF5+UMD") or {}
        a6t = atvw.get("FF5+UMD") or {}
        store[res["expr"]] = {
            "name": res["name"], "expression": res["expr"], "rationale": rat,
            "verdict": res["verdict"], "IC_t": round(res["full"]["IC_t"], 2),
            "mono": round(res["full"]["mono"], 2),
            "VW_FF3_alpha_t": round(a3.get("alpha_t", float("nan")), 2),
            "VW_FF5UMD_alpha_ann": round(a6.get("alpha_ann", float("nan")), 4),
            "VW_FF5UMD_alpha_t": round(a6.get("alpha_t", float("nan")), 2),
            "OOS_VW_FF5UMD_alpha_t": round(a6t.get("alpha_t", float("nan")), 2),
            "updated": datetime.now().strftime("%Y-%m-%d"),
        }
    RATIONALE_JSON.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

    items = list(store.values())

    def _key(x):
        v = x.get("VW_FF5UMD_alpha_t", float("nan"))
        return abs(v) if v == v else 0

    pas = sorted([x for x in items if x["verdict"] == "PASS"], key=_key, reverse=True)
    fail = [x for x in items if x["verdict"] != "PASS"]
    L = [f"# Factor rationale library",
         f"_Economically/financially grounded factors and their explanations. "
         f"{len(items)} total, {len(pas)} validated. Updated {datetime.now():%Y-%m-%d}._\n",
         f"## Validated (PASS): rationale + VALUE-WEIGHTED FF5+UMD alpha significant (full & OOS) + monotone decile\n"]
    for x in pas:
        L += [f"### {x['name']} -- VW FF5+UMD alpha t={x.get('VW_FF5UMD_alpha_t','?')} "
              f"(OOS t={x.get('OOS_VW_FF5UMD_alpha_t','?')}), VW FF3 t={x.get('VW_FF3_alpha_t','?')}, "
              f"IC_t={x['IC_t']}, mono={x['mono']}",
              f"- **Expr:** `{x['expression']}`",
              f"- **Rationale:** {x['rationale']}\n"]
    L += [f"## Has rationale but failed empirical gate (FAIL)\n"]
    for x in fail:
        L += [f"### {x['name']} -- VW FF5+UMD alpha t={x.get('VW_FF5UMD_alpha_t','?')}, "
              f"OOS t={x.get('OOS_VW_FF5UMD_alpha_t','?')}",
              f"- **Expr:** `{x['expression']}`",
              f"- **Rationale:** {x['rationale']}\n"]
    RATIONALE_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"rationale library -> {RATIONALE_MD}  ({len(pas)} validated / {len(items)} total)")


def run_report(factors: dict, outdir=None, start="1972-01-01", split="2000-12-31", update_library=True):
    outdir = Path(outdir) if outdir else ROOT / "results" / f"factor_lab_{datetime.now():%Y%m%d_%H%M%S}"
    outdir.mkdir(parents=True, exist_ok=True)
    summary, all_res = [], []
    for name, (expr, rationale) in factors.items():
        print(f"-- {name} --")
        res = evaluate_factor_full(name, expr, rationale, start, split)
        plot_factor(res, outdir)
        all_res.append(res)
        (outdir / f"{name}.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
        f, te = res["full"], res["test"]
        av = f["vw"]["alphas"] or {}; ae = f["ew"]["alphas"] or {}; atv = te["vw"]["alphas"] or {}
        a3v = av.get("FF3") or {}; a6v = av.get("FF5+UMD") or {}
        a6e = ae.get("FF5+UMD") or {}; a6tv = atv.get("FF5+UMD") or {}
        summary.append({"name": name, "verdict": res["verdict"], "expr": expr,
                        "IC_full": f["IC"], "IC_t_full": f["IC_t"], "mono": f["mono"],
                        "VW_LS_ann": f["vw"]["LS_ann"], "EW_LS_ann": f["ew"]["LS_ann"],
                        "VW_FF3a_t": a3v.get("alpha_t"),
                        "VW_FF5UMDa_ann": a6v.get("alpha_ann"), "VW_FF5UMDa_t": a6v.get("alpha_t"),
                        "EW_FF5UMDa_t": a6e.get("alpha_t"),
                        "IC_test": te["IC"], "VW_FF5UMDa_t_test": a6tv.get("alpha_t"),
                        "VW_LS_SR_test": te["vw"]["LS_SR"]})
        print(f"   {res['verdict']}  IC_t={f['IC_t']:.2f} mono={f['mono']:.2f} | "
              f"VW FF5+UMD alpha={a6v.get('alpha_ann',0)*100:+.1f}%/yr t={a6v.get('alpha_t',0):.2f}  "
              f"(EW t={a6e.get('alpha_t',0):.2f}) | OOS VW FF5+UMD alpha_t={a6tv.get('alpha_t',0):.2f}")
    sdf = pd.DataFrame(summary).sort_values("VW_FF5UMDa_t", key=lambda s: s.abs(), ascending=False)
    sdf.to_csv(outdir / "summary.csv", index=False)
    academic_table(all_res, outdir, split=split)      # VW + EW publication tables
    if update_library:                                # skip for search winners / ad-hoc tests
        update_rationale_library(all_res)             # persist economic explanations (cumulative)
    print(f"\nsaved {len(factors)} factor reports + summary.csv + academic tables -> {outdir}")
    return outdir, sdf


# economic rationale REQUIRED for every factor
DEFAULT_FACTORS = factor_tuples("thesis_core")


if __name__ == "__main__":
    run_report(DEFAULT_FACTORS)


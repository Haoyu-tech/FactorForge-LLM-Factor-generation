# -*- coding: utf-8 -*-
"""Industry-neutral robustness: demean each factor within FF49 industry each month.

Builds a small permno-month -> FF49 industry lookup by streaming just that column
from the Kelly zip (no full-panel rebuild), then re-runs the VW FF5+UMD alpha test on
the industry-neutralized factor. If a factor's alpha survives industry-demeaning, it is
not an industry bet.

Run:
  python adapter/industry_neutral.py --from-json results/llm_all_survivors.json
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()

import factor_lab
from adapter.sp500_loader import compute_factor
from llm_factor.config import path, sample

IND_PARQUET = path("results_root").parent / "data" / "sp500_industry.parquet"


def ensure_industry() -> Path:
    if IND_PARQUET.exists():
        return IND_PARQUET
    pv = pd.read_parquet(path("pv_panel"))
    permno = pv.index.get_level_values("instrument").astype(np.int64)
    dt = pv.index.get_level_values("datetime")
    mkey = set((permno * 1_000_000 + dt.year * 100 + dt.month).values.astype(np.int64))

    zf = zipfile.ZipFile(path("kelly153_zip"))
    inner = next(n for n in zf.namelist() if n.endswith(".parquet"))
    print(f"streaming ff49 industry from {inner} ...")
    parts = []
    with zf.open(inner) as f:
        pf = pq.ParquetFile(f)
        for i in range(pf.num_row_groups):
            df = pf.read_row_group(i, columns=["permno", "eom", "ff49"]).to_pandas().dropna(subset=["permno", "eom"])
            eom = pd.to_datetime(df["eom"])
            k = (df["permno"].astype(np.int64) * 1_000_000 + eom.dt.year * 100 + eom.dt.month)
            m = np.fromiter((kk in mkey for kk in k.values), dtype=bool, count=len(k))
            if m.any():
                sub = df.loc[m, ["permno", "ff49"]].copy()
                sub["datetime"] = eom[m].values
                sub["instrument"] = sub["permno"].astype(np.int64).astype(str)
                parts.append(sub[["datetime", "instrument", "ff49"]])
    ind = pd.concat(parts, ignore_index=True).set_index(["datetime", "instrument"])["ff49"]
    IND_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    ind.to_frame().to_parquet(IND_PARQUET)
    print(f"saved industry lookup -> {IND_PARQUET}  ({len(ind):,} rows)")
    return IND_PARQUET


def load_industry() -> pd.Series:
    ensure_industry()
    return pd.read_parquet(IND_PARQUET)["ff49"]


def industry_neutralize(fac: pd.Series, ind: pd.Series) -> pd.Series:
    df = pd.DataFrame({"f": fac, "ind": ind}).replace([np.inf, -np.inf], np.nan).dropna()
    grp = df.groupby([df.index.get_level_values("datetime"), "ind"])["f"]
    return (df["f"] - grp.transform("mean")).rename("f")


def _alpha_t(ls_full, split):
    a_full = (factor_lab._alphas(ls_full) or {}).get("FF5+UMD") or {}
    oos = ls_full[ls_full.index.get_level_values("datetime") >= pd.Timestamp(split)] if isinstance(ls_full.index, pd.MultiIndex) else ls_full[ls_full.index >= pd.Timestamp(split)]
    a_oos = (factor_lab._alphas(oos) or {}).get("FF5+UMD") or {}
    return a_full.get("alpha_t"), a_oos.get("alpha_t")


def run(factors: dict, outdir=None, start=None, split=None) -> Path:
    start = start or sample("start", "1972-01-01")
    split = split or sample("split", "2000-12-31")
    outdir = Path(outdir) if outdir else (path("results_root") / "industry_neutral")
    outdir.mkdir(parents=True, exist_ok=True)
    ind = load_industry()
    me = factor_lab.load_me()
    label = factor_lab.load_labels()

    rows = []
    for name, expr in factors.items():
        fac = compute_factor(expr)
        fac = fac[fac.index.get_level_values("datetime") >= pd.Timestamp(start)]
        # raw VW alpha
        _, ls_raw = factor_lab._deciles(fac, label, weights=me)
        rt_full, rt_oos = _alpha_t(ls_raw, split)
        # industry-neutralized VW alpha
        facn = industry_neutralize(fac, ind)
        _, ls_neu = factor_lab._deciles(facn, label, weights=me)
        nt_full, nt_oos = _alpha_t(ls_neu, split)
        rows.append({"name": name, "raw_a_t_full": rt_full, "raw_a_t_oos": rt_oos,
                     "indneu_a_t_full": nt_full, "indneu_a_t_oos": nt_oos})
        print(f"-- {name:26} raw VW a_t full/oos={rt_full:+.2f}/{rt_oos:+.2f}  "
              f"-> industry-neutral {nt_full:+.2f}/{nt_oos:+.2f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(outdir / "industry_neutral.csv", index=False)
    L = ["# Industry-neutral robustness (FF49)", "",
         "VW FF5+UMD alpha t before vs after demeaning the factor within FF49 industry each month.", "",
         "| Factor | raw full/OOS | industry-neutral full/OOS |", "|---|--:|--:|"]
    for _, r in df.iterrows():
        L.append(f"| {r['name']} | {r['raw_a_t_full']:+.2f} / {r['raw_a_t_oos']:+.2f} | "
                 f"{r['indneu_a_t_full']:+.2f} / {r['indneu_a_t_oos']:+.2f} |")
    (outdir / "industry_neutral.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\nindustry-neutral tables -> {outdir}")
    return outdir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()
    data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    facs = data["factors"] if isinstance(data, dict) else data
    run({c["name"]: c["expression"] for c in facs}, outdir=args.outdir)

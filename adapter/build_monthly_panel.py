# -*- coding: utf-8 -*-
"""
Build the MONTHLY multi-factor panel that QuantaAlpha will mine, restricted to
point-in-time S&P 500 members.

Input :
  - WRDS kelly_us_sample.parquet      (monthly JKP/Kelly characteristics, US)
  - data/sp500_membership.parquet     (from build_sp500_membership.py)
Output:
  - data/sp500_monthly.parquet
      MultiIndex (datetime=eom, instrument=permno-str)
      feature columns prefixed with '$'  (e.g. $close, $me, $be_me, $gp_at ...)
      plus 'label' = ret_exc_lead1m (next-month excess return)

This is the drop-in replacement for QuantaAlpha's qlib `daily_pv` -- same shape
(MultiIndex + $-columns) but MONTHLY and with many data types beyond price/volume.
"""
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from llm_factor.config import path

KELLY = path("kelly_us_sample")
MEMBERS = path("membership_panel")
OUT = path("legacy_panel")

# identity / meta columns that are NOT factors
META = {"eom", "excntry", "common", "primary_sec", "permno"}
LABEL = "ret_exc_lead1m"          # next-month excess return -> prediction target

# columns we expose under conventional price/volume names so that standard
# QuantaAlpha price expressions still parse on monthly data
RENAME = {
    "prc_local": "close",         # monthly price -> $close
    "ret_1_0": "return",          # contemporaneous monthly return -> $return
    "me": "me",                   # market equity (size)
}


def sp500_filter(df: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    """Keep (permno, eom) rows that fall inside an S&P 500 membership spell."""
    m = df.merge(members[["permno", "mbr_start", "mbr_end"]], on="permno", how="inner")
    keep = (m["eom"] >= m["mbr_start"]) & (m["eom"] <= m["mbr_end"])
    m = m[keep].drop(columns=["mbr_start", "mbr_end"])
    # a permno could match >1 spell in pathological cases -> dedup
    return m.drop_duplicates(subset=["permno", "eom"])


def main():
    print("Loading kelly_us_sample ...")
    df = pd.read_parquet(KELLY)
    df["eom"] = pd.to_datetime(df["eom"])
    df = df.dropna(subset=["permno"]).copy()
    df["permno"] = df["permno"].astype(np.int64)
    print(f"  kelly rows: {len(df):,}  cols: {len(df.columns)}")

    members = pd.read_parquet(MEMBERS)
    df = sp500_filter(df, members)
    print(f"  after S&P 500 filter: {len(df):,} rows, "
          f"{df['permno'].nunique()} permnos, "
          f"{df['eom'].min().date()} -> {df['eom'].max().date()}")

    # feature columns = everything except meta + label
    feat_cols = [c for c in df.columns if c not in META and c != LABEL]

    out = pd.DataFrame(index=df.index)
    for c in feat_cols:
        name = RENAME.get(c, c)
        out[f"${name}"] = pd.to_numeric(df[c], errors="coerce")

    out["label"] = pd.to_numeric(df[LABEL], errors="coerce")
    out["datetime"] = df["eom"].values
    out["instrument"] = df["permno"].astype(str).values

    out = out.set_index(["datetime", "instrument"]).sort_index()
    # drop rows where every $ feature is missing (nothing to compute on)
    dollar = [c for c in out.columns if c.startswith("$")]
    out = out[out[dollar].notna().any(axis=1)]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT)

    dollar_cols = [c for c in out.columns if c.startswith("$")]
    print(f"\nSaved -> {OUT}")
    print(f"  rows           : {len(out):,}")
    print(f"  $ feature cols : {len(dollar_cols)}")
    print(f"  months         : {out.index.get_level_values('datetime').nunique()}")
    print(f"  avg stocks/mo  : {len(out)/out.index.get_level_values('datetime').nunique():.0f}")
    print(f"  features       : {dollar_cols}")
    print(f"  label missing% : {out['label'].isna().mean()*100:.1f}%")


if __name__ == "__main__":
    main()


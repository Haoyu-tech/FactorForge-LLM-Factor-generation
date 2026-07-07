# -*- coding: utf-8 -*-
"""
Build the FULL-universe monthly price/volume panel: every official S&P 500
member, every month (~500/month, no characteristic-join dropouts).

Source: CRSP "S&P 500 Index Constituents" file - it already carries the daily
price/volume of exactly the index members plus their membership windows. We
resample its DAILY data to MONTHLY bars and keep only member-months.

Output: data/sp500_monthly_pv.parquet
  MultiIndex (datetime=month-end, instrument=permno-str)
  $open $high $low $close $volume $me $return $shrout  +  label(next-month ret)
"""
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from llm_factor.config import path

SRC = path("sp500_constituents_zip")
MEMBERS = path("membership_panel")
OUT = path("pv_panel")

USE = ["PERMNO", "Ticker", "DlyCalDt", "DlyClose", "DlyOpen", "DlyHigh",
       "DlyLow", "DlyVol", "DlyCap", "DlyRet", "ShrOut"]
NUM = ["DlyClose", "DlyOpen", "DlyHigh", "DlyLow", "DlyVol", "DlyCap", "DlyRet", "ShrOut"]


def main():
    zf = zipfile.ZipFile(SRC)
    member = zf.namelist()[0]
    print(f"Reading daily member data: {SRC.name} :: {member}")
    with zf.open(member) as fh:
        df = pd.read_csv(fh, usecols=USE, dtype={"PERMNO": "int64", "Ticker": "string"})
    print(f"  daily rows: {len(df):,}")

    df["DlyCalDt"] = pd.to_datetime(df["DlyCalDt"])
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ym"] = df["DlyCalDt"].dt.to_period("M")
    df = df.sort_values(["PERMNO", "DlyCalDt"])

    # monthly OHLCV bar per (permno, month)
    g = df.groupby(["PERMNO", "ym"], sort=True)
    monthly = g.agg(
        eom_trade=("DlyCalDt", "last"),
        close=("DlyClose", "last"),
        open=("DlyOpen", "first"),
        high=("DlyHigh", "max"),
        low=("DlyLow", "min"),
        volume=("DlyVol", "sum"),
        cap=("DlyCap", "last"),
        shrout=("ShrOut", "last"),
        ticker=("Ticker", "last"),
    )
    # monthly return = compound daily (vectorised via log1p sum)
    df["l1p"] = np.log1p(df["DlyRet"])
    monthly["ret"] = np.expm1(g["l1p"].sum(min_count=1))
    monthly = monthly.reset_index()

    # calendar month-end as the index date (aligns with kelly eom convention)
    monthly["datetime"] = monthly["ym"].dt.to_timestamp(how="end").dt.normalize()

    # keep only member-months (point-in-time official list)
    mem = pd.read_parquet(MEMBERS)
    m = monthly.merge(mem[["permno", "mbr_start", "mbr_end"]],
                      left_on="PERMNO", right_on="permno", how="inner")
    keep = (m["datetime"] >= m["mbr_start"]) & (m["datetime"] <= m["mbr_end"])
    m = m[keep].drop_duplicates(subset=["PERMNO", "datetime"])

    # forward 1-month return label (next consecutive member-month)
    m = m.sort_values(["PERMNO", "datetime"])
    m["label"] = m.groupby("PERMNO")["ret"].shift(-1)

    out = pd.DataFrame({
        "datetime": m["datetime"].values,
        "instrument": m["PERMNO"].astype(str).values,
        "$open": m["open"].values,
        "$high": m["high"].values,
        "$low": m["low"].values,
        "$close": m["close"].values,
        "$volume": m["volume"].values,
        "$me": m["cap"].values,
        "$return": m["ret"].values,
        "$shrout": m["shrout"].values,
        "label": m["label"].values,
    }).set_index(["datetime", "instrument"]).sort_index()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT)

    # report per-month coverage
    cnt = out.groupby(level="datetime").size()
    print(f"\nSaved -> {OUT}")
    print(f"  rows        : {len(out):,}")
    print(f"  months      : {cnt.size}  ({out.index.get_level_values('datetime').min().date()} -> "
          f"{out.index.get_level_values('datetime').max().date()})")
    print(f"  names/month : min {cnt.min()}, median {int(cnt.median())}, max {cnt.max()}")
    for d in ["1995-06-30", "2005-06-30", "2015-06-30", "2020-06-30"]:
        d = pd.Timestamp(d)
        n = cnt.get(d, 0)
        print(f"    {d.date()}: {n} names")
    print(f"  label miss% : {out['label'].isna().mean()*100:.1f}%  (mostly last index-month of each name)")


if __name__ == "__main__":
    main()


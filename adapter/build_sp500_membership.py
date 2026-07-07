# -*- coding: utf-8 -*-
"""
Build point-in-time S&P 500 membership table from the CRSP
"S&P 500 Index Constituents" file.

Source : WRDS / CRSP / Index - Version 2 / S&P 500 Index Constituents.zip
Output : data/sp500_membership.parquet  (one row per membership spell)
         columns: permno, ticker, mbr_start, mbr_end

The CRSP file is a daily panel; each row repeats the membership window
(MbrStartDt, MbrEndDt) for a PERMNO, so we just take the distinct spells.
"""
import zipfile
from pathlib import Path

import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from llm_factor.config import path

SRC = path("sp500_constituents_zip")
OUT = path("membership_panel")


def main():
    zf = zipfile.ZipFile(SRC)
    member = zf.namelist()[0]
    print(f"Reading {SRC.name} :: {member}")

    use = ["PERMNO", "Ticker", "MbrStartDt", "MbrEndDt"]
    with zf.open(member) as fh:
        df = pd.read_csv(fh, usecols=use, dtype=str)
    print(f"  raw rows: {len(df):,}")

    # Ticker can change within a spell -> keep the most frequent ticker per
    # (permno, start, end) so the spell table stays one row per spell.
    df["MbrStartDt"] = pd.to_datetime(df["MbrStartDt"])
    df["MbrEndDt"] = pd.to_datetime(df["MbrEndDt"])
    df["PERMNO"] = df["PERMNO"].astype(int)

    tick = (
        df.dropna(subset=["Ticker"])
        .groupby(["PERMNO", "MbrStartDt", "MbrEndDt"])["Ticker"]
        .agg(lambda s: s.value_counts().index[0])
        .reset_index()
    )

    spells = (
        df[["PERMNO", "MbrStartDt", "MbrEndDt"]]
        .drop_duplicates()
        .merge(tick, on=["PERMNO", "MbrStartDt", "MbrEndDt"], how="left")
        .rename(columns={
            "PERMNO": "permno",
            "Ticker": "ticker",
            "MbrStartDt": "mbr_start",
            "MbrEndDt": "mbr_end",
        })
        .sort_values(["permno", "mbr_start"])
        .reset_index(drop=True)
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    spells.to_parquet(OUT, index=False)

    print(f"  spells           : {len(spells):,}")
    print(f"  distinct permnos : {spells['permno'].nunique():,}")
    print(f"  date span        : {spells['mbr_start'].min().date()} -> {spells['mbr_end'].max().date()}")
    # sanity: active count at a recent month-end
    for d in ["2000-12-31", "2010-12-31", "2020-06-30"]:
        d = pd.Timestamp(d)
        n = spells[(spells.mbr_start <= d) & (spells.mbr_end >= d)]["permno"].nunique()
        print(f"  active on {d.date()}: {n}")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()


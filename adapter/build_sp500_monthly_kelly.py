# -*- coding: utf-8 -*-
"""
Build the working panel: FULL official S&P 500 universe (~500/month, 1965+)
with the USABLE set of Kelly-153 characteristics merged in.

- Universe + price/volume + label : data/sp500_monthly_pv.parquet (CRSP, full list)
- Characteristics                 : Kelly_factor_153, the usable set from
  configs/kelly_usable_factors.json (<=10% missing on SP500 member-months, 1972-2025;
  see data/kelly153_coverage.csv). Identifiers / raw prices / returns / the forward
  return `ret_exc_lead1m` are excluded upstream when the usable list is built.
Output: data/sp500_monthly_kelly.parquet  (becomes the loader default)

Char window is Kelly's (~1972-2025); pre-1972 chars are NaN but the price/volume +
label still cover the full universe 1965+.
"""
import json
import time
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
from llm_factor.config import path

PV = path("pv_panel")
LOCAL153 = path("kelly153")
KELLY_ZIP = path("kelly153_zip")
OUT = path("panel")
START = pd.Timestamp("1965-01-01")

# usable Kelly characteristics (single source of truth; built by the coverage audit)
FEATS = json.loads(path("kelly_usable_factors").read_text(encoding="utf-8"))


def ensure_kelly_extract() -> Path:
    """Return a readable Kelly-153 parquet, extracting it from the zip if needed."""
    if LOCAL153.exists():
        return LOCAL153
    if not KELLY_ZIP.exists():
        raise FileNotFoundError(
            f"neither the Kelly extract ({LOCAL153}) nor the zip ({KELLY_ZIP}) exists; "
            "set LLM_FACTOR_KELLY153 or LLM_FACTOR_KELLY153_ZIP.")
    LOCAL153.parent.mkdir(parents=True, exist_ok=True)
    print(f"extracting Kelly-153 parquet from {KELLY_ZIP} -> {LOCAL153} ...")
    with zipfile.ZipFile(KELLY_ZIP) as z:
        inner = next(n for n in z.namelist() if n.endswith(".parquet"))
        with z.open(inner) as src, open(LOCAL153, "wb") as dst:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                dst.write(chunk)
    return LOCAL153


def main():
    pv = pd.read_parquet(PV)
    pv = pv[pv.index.get_level_values("datetime") >= START]
    spine = pd.DataFrame({
        "permno": pv.index.get_level_values("instrument").astype(np.int64),
        "datetime": pv.index.get_level_values("datetime"),
    })
    mkey = set((spine.permno * 1_000_000 + spine.datetime.dt.year * 100
                + spine.datetime.dt.month).values.astype(np.int64))

    extract = ensure_kelly_extract()
    print(f"streaming Kelly153 for {len(FEATS)} usable factors ...")
    pf = pq.ParquetFile(extract)
    chunks = []
    t = time.time()
    for i in range(pf.num_row_groups):
        df = pf.read_row_group(i, columns=["permno", "eom"] + FEATS).to_pandas()
        df = df.dropna(subset=["permno", "eom"])
        eom = pd.to_datetime(df["eom"])
        k = (df["permno"].astype(np.int64) * 1_000_000 + eom.dt.year * 100 + eom.dt.month)
        m = np.fromiter((kk in mkey for kk in k.values), dtype=bool, count=len(k))
        if m.any():
            sub = df.loc[m, ["permno"] + FEATS].copy()
            sub["datetime"] = eom[m].values
            sub["permno"] = sub["permno"].astype(np.int64)
            chunks.append(sub)
    chars = pd.concat(chunks, ignore_index=True)
    print(f"  matched char rows: {len(chars):,} [{time.time()-t:.0f}s]")

    chars["instrument"] = chars["permno"].astype(str)
    chars = chars.drop(columns="permno").rename(columns={c: f"${c}" for c in FEATS})
    chars = chars.set_index(["datetime", "instrument"])

    out = pv.join(chars, how="left")  # keep full universe; chars NaN where absent
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT)

    dollar = [c for c in out.columns if c.startswith("$")]
    print(f"\nSaved -> {OUT}")
    print(f"  rows         : {len(out):,}")
    print(f"  $ features   : {len(dollar)}  (PV + {len(FEATS)} Kelly chars)")
    print(f"  window       : {out.index.get_level_values('datetime').min().date()} -> "
          f"{out.index.get_level_values('datetime').max().date()}")
    kera = out[(out.index.get_level_values('datetime') >= '1972-01-31') &
               (out.index.get_level_values('datetime') <= '2025-12-31')]
    miss = pd.Series({f: kera['$'+f].isna().mean() for f in FEATS}).sort_values()
    print("\n  char missing% on SP500 member-months (1972-2025):")
    print(f"    factors: {len(FEATS)}  median miss {miss.median()*100:.1f}%  "
          f"max miss {miss.max()*100:.1f}%  (worst: {miss.idxmax()})")


if __name__ == "__main__":
    main()


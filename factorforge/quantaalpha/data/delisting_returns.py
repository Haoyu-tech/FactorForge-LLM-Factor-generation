"""CRSP delisting-return normalization and in-place Qlib feature upgrade."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


def load_delisting_returns(wrds_root: str | Path) -> pd.DataFrame:
    """Return one CRSP delisting return per PERMNO/date using standard imputation.

    Observed DLRET is retained.  A missing performance-related delisting return
    (DLSTCD 500 or 520--584) is set to -30% on NYSE/AMEX and -55% on NASDAQ;
    other missing values are zero.  Values are bounded below by -100%.
    """
    root = Path(wrds_root)
    legacy = root / "CRSP" / "Legacy Data  Stock  Events" / "CRSP Stock Events - Delisting Information.zip"
    modern = root / "CRSP" / "Stock - Version 2" / "Delisting Information.zip"
    with zipfile.ZipFile(legacy) as archive:
        member = next(x for x in archive.infolist() if not x.is_dir())
        with archive.open(member) as stream:
            old = pd.read_csv(stream, usecols=["PERMNO", "DLSTDT", "DLSTCD", "DLRET", "HEXCD"], low_memory=False)
    old.columns = ["permno", "date", "code", "legacy_return", "exchange"]
    old["date"] = pd.to_datetime(old["date"], errors="coerce")
    for col in ["permno", "code", "legacy_return", "exchange"]:
        old[col] = pd.to_numeric(old[col], errors="coerce")

    # Version 2 is preferred for observed values and dates; legacy codes are
    # retained solely for the accepted missing-return imputation rule.
    with zipfile.ZipFile(modern) as archive:
        member = next(x for x in archive.infolist() if not x.is_dir())
        with archive.open(member) as stream:
            new = pd.read_csv(stream, usecols=["PERMNO", "DelistingDt", "DelRet", "PrimaryExch"], low_memory=False)
    new.columns = ["permno", "date", "modern_return", "primary_exchange"]
    new["date"] = pd.to_datetime(new["date"], errors="coerce")
    new["permno"] = pd.to_numeric(new["permno"], errors="coerce")
    new["modern_return"] = pd.to_numeric(new["modern_return"], errors="coerce")
    data = old.merge(new, on=["permno", "date"], how="outer")
    data["delist_return"] = data["modern_return"].combine_first(data["legacy_return"])
    performance = (data["code"] == 500) | data["code"].between(520, 584, inclusive="both")
    missing = data["delist_return"].isna()
    nasdaq = (data["exchange"] == 3) | data["primary_exchange"].astype(str).str.upper().eq("Q")
    data.loc[missing & performance & nasdaq, "delist_return"] = -0.55
    data.loc[missing & performance & ~nasdaq, "delist_return"] = -0.30
    data.loc[data["delist_return"].isna(), "delist_return"] = 0.0
    data["delist_return"] = data["delist_return"].clip(lower=-1.0)
    return data.dropna(subset=["permno", "date"]).sort_values(["permno", "date"])


def combine_return(regular, delisting):
    regular = pd.to_numeric(regular, errors="coerce")
    delisting = pd.to_numeric(delisting, errors="coerce").fillna(0.0)
    return ((1.0 + regular.fillna(0.0)) * (1.0 + delisting) - 1.0).where(regular.notna() | delisting.ne(0.0))


def patch_qlib_features(wrds_root: str | Path, qlib_dir: str | Path) -> dict:
    """Add ``ret_total`` and ``delist_return`` to an existing WRDS Qlib store."""
    qlib = Path(qlib_dir)
    calendar = pd.to_datetime(pd.read_csv(qlib / "calendars" / "day.txt", header=None)[0])
    date_to_pos = {pd.Timestamp(value): pos for pos, value in enumerate(calendar)}
    events = load_delisting_returns(wrds_root)
    event_map: dict[int, list[tuple[pd.Timestamp, float]]] = {}
    for row in events.itertuples(index=False):
        event_map.setdefault(int(row.permno), []).append((pd.Timestamp(row.date), float(row.delist_return)))
    feature_root = qlib / "features"
    patched = events_applied = events_outside = 0
    for directory in feature_root.iterdir():
        if not directory.is_dir():
            continue
        change_path = directory / "change.day.bin"
        if not change_path.exists():
            continue
        raw = np.fromfile(change_path, dtype=np.float32)
        if raw.size < 2:
            continue
        start = int(raw[0])
        regular = raw[1:].astype(np.float64)
        total = regular.copy()
        delist = np.full(regular.size, np.nan, dtype=np.float64)
        name = directory.name.lower()
        permno = int(name[1:]) if name.startswith("p") and name[1:].isdigit() else None
        if permno is not None:
            for date, value in event_map.get(permno, []):
                if date not in date_to_pos:
                    continue
                offset = date_to_pos[date] - start
                if 0 <= offset < regular.size:
                    base = regular[offset]
                    total[offset] = (1.0 + (base if np.isfinite(base) else 0.0)) * (1.0 + value) - 1.0
                    delist[offset] = value
                    events_applied += 1
                else:
                    events_outside += 1
        np.concatenate(([start], total)).astype(np.float32).tofile(directory / "ret_total.day.bin")
        np.concatenate(([start], delist)).astype(np.float32).tofile(directory / "delist_return.day.bin")
        patched += 1
    report = {"feature_directories": patched, "events_applied": events_applied, "events_outside_feature_range": events_outside}
    (qlib / "delisting_return_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wrds-root", required=True)
    parser.add_argument("--qlib-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(patch_qlib_features(args.wrds_root, args.qlib_dir), indent=2))

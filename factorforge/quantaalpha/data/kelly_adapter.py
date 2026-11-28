"""JKP/Kelly 153-factor adapter for the historical S&P 500 universe."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ID_COLUMNS = ["permno", "eom", "ret_exc_lead1m", "ret_exc", "me"]
FIRST_FACTOR = "prc"
EXPECTED_FACTOR_COUNT = 153
DEFAULT_WRDS_ROOT = "/mnt/d/桌面文件/US stock research/wrds"
# Raw JKP file locations relative to WRDS_ROOT, tried in order when
# KELLY_SOURCE_PATH is unset.
SOURCE_CANDIDATES = (
    Path("kelley_factors") / "kelly_factor_153.parquet",
    Path("kelly_factors") / "kelly_factor_153.parquet",
    Path("Kelly_factor_153.parquet"),
    Path("kelly_factor_153.parquet"),
)


def resolve_kelly_paths(dotenv: dict, project_root: str | Path) -> dict[str, Path]:
    """Single source of truth for Kelly paths used by the backend and CLI.

    Overrides: KELLY_SOURCE_PATH (raw JKP parquet), KELLY_PANEL_PATH (filtered
    S&P 500 cache). Membership comes from the WRDS-built Qlib instruments file.
    """
    project_root = Path(project_root)
    wrds_root = Path(dotenv.get("WRDS_ROOT") or DEFAULT_WRDS_ROOT)
    if dotenv.get("KELLY_SOURCE_PATH"):
        source = Path(dotenv["KELLY_SOURCE_PATH"])
    else:
        candidates = [wrds_root / relative for relative in SOURCE_CANDIDATES]
        source = next((path for path in candidates if path.exists()), candidates[0])
    panel = Path(
        dotenv.get("KELLY_PANEL_PATH")
        or wrds_root / "_quantaalpha_cache" / "kelly_153_sp500.parquet"
    )
    qlib_dir = Path(
        dotenv.get("WRDS_QLIB_DATA_DIR") or project_root / "data" / "qlib" / "wrds_sp500"
    )
    report_dir = project_root / "data" / "kelly"
    return {
        "source": source,
        "panel": panel,
        "membership": qlib_dir / "instruments" / "sp500.txt",
        "report_json": report_dir / "jkp_sp500_missingness_1987.json",
        "report_csv": report_dir / "jkp_sp500_missingness_1987.csv",
    }


def load_membership_intervals(path: str | Path) -> dict[int, list[tuple[np.datetime64, np.datetime64]]]:
    intervals: dict[int, list[tuple[np.datetime64, np.datetime64]]] = defaultdict(list)
    with Path(path).open("r", encoding="utf-8") as stream:
        for raw in stream:
            parts = raw.strip().split()
            if len(parts) < 3 or not parts[0].upper().startswith("P"):
                continue
            try:
                permno = int(parts[0][1:])
                start = np.datetime64(parts[1], "ns")
                end = np.datetime64(parts[2], "ns")
            except (TypeError, ValueError):
                continue
            intervals[permno].append((start, end))
    return dict(intervals)


def historical_member_mask(
    permno: pd.Series,
    dates: pd.Series,
    intervals: dict[int, list[tuple[np.datetime64, np.datetime64]]],
) -> np.ndarray:
    numeric_permno = pd.to_numeric(permno, errors="coerce")
    date_values = pd.to_datetime(dates, errors="coerce").to_numpy(dtype="datetime64[ns]")
    candidate = numeric_permno.isin(intervals).to_numpy()
    mask = np.zeros(len(numeric_permno), dtype=bool)
    if not candidate.any():
        return mask
    values = numeric_permno.to_numpy()
    for identifier in pd.unique(values[candidate]):
        if pd.isna(identifier):
            continue
        positions = np.flatnonzero(candidate & (values == identifier))
        member_dates = date_values[positions]
        accepted = np.zeros(len(positions), dtype=bool)
        for start, end in intervals[int(identifier)]:
            accepted |= (member_dates >= start) & (member_dates <= end)
        mask[positions] = accepted
    return mask


def factor_columns(parquet_file: pq.ParquetFile) -> list[str]:
    names = parquet_file.schema_arrow.names
    if FIRST_FACTOR not in names:
        raise ValueError(f"Expected first JKP factor {FIRST_FACTOR!r}")
    columns = names[names.index(FIRST_FACTOR):]
    if len(columns) != EXPECTED_FACTOR_COUNT:
        raise ValueError(f"Expected {EXPECTED_FACTOR_COUNT} JKP factors, found {len(columns)}")
    return columns


def build_sp500_panel(
    source: str | Path,
    membership_file: str | Path,
    output: str | Path,
    report_csv: str | Path,
    report_json: str | Path,
    start_month: str | None = None,
) -> dict:
    """Filter the raw JKP panel to historical S&P 500 member-months.

    ``start_month`` (inclusive) drops earlier months so the missingness report
    describes the same history the expanding backtest trains on.
    """
    start = pd.Timestamp(start_month) if start_month else None
    source = Path(source)
    output = Path(output)
    report_csv = Path(report_csv)
    report_json = Path(report_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    intervals = load_membership_intervals(membership_file)
    parquet_file = pq.ParquetFile(source)
    factors = factor_columns(parquet_file)
    read_columns = list(dict.fromkeys([*ID_COLUMNS, *factors]))

    total_rows = 0
    model_rows = 0
    nonmissing = pd.Series(0, index=factors, dtype="int64")
    model_nonmissing = pd.Series(0, index=factors, dtype="int64")
    first_valid: dict[str, pd.Timestamp] = {}
    last_valid: dict[str, pd.Timestamp] = {}
    writer: pq.ParquetWriter | None = None
    partial = output.with_suffix(output.suffix + ".partial")
    if partial.exists():
        partial.unlink()

    try:
        for row_group in range(parquet_file.metadata.num_row_groups):
            frame = parquet_file.read_row_group(row_group, columns=read_columns).to_pandas()
            frame["eom"] = pd.to_datetime(frame["eom"], errors="coerce")
            mask = historical_member_mask(frame["permno"], frame["eom"], intervals)
            if start is not None:
                mask &= (frame["eom"] >= start).to_numpy()
            frame = frame.loc[mask, read_columns].copy()
            if frame.empty:
                continue
            frame["permno"] = pd.to_numeric(frame["permno"], errors="coerce").astype("Int64")
            frame = frame.dropna(subset=["permno", "eom"]).sort_values(["eom", "permno"])
            if frame.empty:
                continue
            # Source row groups use different Decimal precision for a few
            # characteristics. A stable float schema is appropriate for ML and
            # keeps the filtered panel compact.
            frame[factors] = frame[factors].apply(pd.to_numeric, errors="coerce").astype("float32")
            for column in ("ret_exc_lead1m", "ret_exc", "me"):
                frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float32")

            total_rows += len(frame)
            valid = frame[factors].notna()
            nonmissing = nonmissing.add(valid.sum().astype("int64"), fill_value=0).astype("int64")
            label_mask = frame["ret_exc_lead1m"].notna()
            model_rows += int(label_mask.sum())
            if label_mask.any():
                model_nonmissing = model_nonmissing.add(
                    valid.loc[label_mask].sum().astype("int64"), fill_value=0
                ).astype("int64")

            dates = frame["eom"]
            for factor in factors:
                factor_dates = dates[valid[factor]]
                if factor_dates.empty:
                    continue
                minimum, maximum = factor_dates.min(), factor_dates.max()
                if factor not in first_valid or minimum < first_valid[factor]:
                    first_valid[factor] = minimum
                if factor not in last_valid or maximum > last_valid[factor]:
                    last_valid[factor] = maximum

            table = pa.Table.from_pandas(frame, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(
                    partial, table.schema, compression="zstd",
                    use_dictionary=True, write_statistics=True,
                )
            writer.write_table(table)
            print(
                f"[{row_group + 1}/{parquet_file.metadata.num_row_groups}] "
                f"S&P500 rows={total_rows:,}",
                flush=True,
            )
    finally:
        if writer is not None:
            writer.close()

    if total_rows == 0 or writer is None:
        raise RuntimeError("No historical S&P 500 rows overlapped the Kelly panel")
    partial.replace(output)

    report = pd.DataFrame({
        "factor": factors,
        "missing_rate_sp500": [1.0 - nonmissing[name] / total_rows for name in factors],
        "missing_rate_model_sample": [
            1.0 - model_nonmissing[name] / model_rows if model_rows else np.nan
            for name in factors
        ],
        "nonmissing_sp500": [int(nonmissing[name]) for name in factors],
        "nonmissing_model_sample": [int(model_nonmissing[name]) for name in factors],
        "first_valid_month": [
            first_valid.get(name).date().isoformat() if name in first_valid else None
            for name in factors
        ],
        "last_valid_month": [
            last_valid.get(name).date().isoformat() if name in last_valid else None
            for name in factors
        ],
    }).sort_values(["missing_rate_model_sample", "factor"], kind="stable")
    report.to_csv(report_csv, index=False)

    summary = {
        "source": str(source),
        "output": str(output),
        "factor_count": len(factors),
        "sp500_member_months": total_rows,
        "model_rows_with_forward_return": model_rows,
        "start_month": str(pq.read_table(output, columns=["eom"]).column("eom").to_pandas().min().date()),
        "end_month": str(pq.read_table(output, columns=["eom"]).column("eom").to_pandas().max().date()),
        "threshold_counts": {
            str(threshold): int((report["missing_rate_model_sample"] <= threshold).sum())
            for threshold in (0.1, 0.2, 0.3, 0.4, 0.5)
        },
        "report_csv": str(report_csv),
    }
    report_json.write_text(
        json.dumps({"summary": summary, "factors": report.to_dict("records")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def main(argv: Iterable[str] | None = None) -> None:
    """Build the cache. Paths default to what the backend reads (see resolve_kelly_paths)."""
    import os

    project_root = Path(__file__).resolve().parents[2]
    dotenv: dict[str, str] = {}
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                dotenv[key.strip()] = value.strip().strip("'\"")
    dotenv.update({key: value for key, value in os.environ.items()
                   if key in {"WRDS_ROOT", "WRDS_QLIB_DATA_DIR", "KELLY_SOURCE_PATH", "KELLY_PANEL_PATH"}})
    defaults = resolve_kelly_paths(dotenv, project_root)

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(defaults["source"]))
    parser.add_argument("--membership", default=str(defaults["membership"]))
    parser.add_argument("--output", default=str(defaults["panel"]))
    parser.add_argument("--report-csv", default=str(defaults["report_csv"]))
    parser.add_argument("--report-json", default=str(defaults["report_json"]))
    parser.add_argument(
        "--start-month",
        default=dotenv.get("US_TRAIN_START_DATE") or dotenv.get("TRAIN_START_DATE") or "1987-01-01",
        help="First month kept (inclusive); pass '' to keep the full history",
    )
    args = parser.parse_args(argv)
    for label, path in (("source", args.source), ("membership", args.membership)):
        if not Path(path).exists():
            raise SystemExit(f"Kelly {label} file not found: {path}")
    build_sp500_panel(
        args.source, args.membership, args.output,
        args.report_csv, args.report_json,
        start_month=args.start_month or None,
    )


if __name__ == "__main__":
    main()

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
) -> dict:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--membership", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-csv", required=True)
    parser.add_argument("--report-json", required=True)
    args = parser.parse_args(argv)
    build_sp500_panel(
        args.source, args.membership, args.output,
        args.report_csv, args.report_json,
    )


if __name__ == "__main__":
    main()

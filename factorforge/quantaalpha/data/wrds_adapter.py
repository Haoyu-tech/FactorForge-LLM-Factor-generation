"""WRDS data catalog and S&P 500-to-Qlib builder."""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd

SP500_REL = Path("CRSP/Index - Version 2/S&P 500 Index Constituents.zip")
SP500_INDEX_REL = Path("CRSP/Index - Version 2/CRSP Daily Index and Portfolios on S&P 500.zip")
FF3_REL = Path("CRSP/FamaFactor/Fama-French 3 Factors Plus Momentum - Daily Frequency.zip")
FF5_REL = Path("CRSP/FamaFactor/5 Factors Plus Momentum - Daily Frequency.zip")
FUNDQ_REL = Path("CRSP/CRSPCompustat Merged Database/CRSP Compustat Merged Database Fundamentals Quarterly.zip")
LINK_REL = Path("CRSP/CRSPCompustat Merged Database/CRSP Compustat Merged Database Linking Table.zip")

# Quarterly fields exposed to factor formulas. This first expansion is
# deliberately limited to fields with consistently low S&P 500 missing rates.
RAW_QUARTERLY_FIELDS = [
    "atq", "saleq", "niq", "ceqq",
    "invtq", "rectq", "ppentq", "ltq", "req", "oiadpq",
]
DERIVED_QUARTERLY_FIELDS = [
    "roa_q", "roe_q", "gross_profitability_q", "operating_profitability_q",
    "leverage_q", "cash_to_assets_q", "asset_growth_q", "sales_growth_q",
    "earnings_growth_q", "operating_income_growth_q", "inventory_change_to_assets_q",
    "receivables_change_to_assets_q", "ppent_change_to_assets_q", "inventory_to_sales_q",
    "receivables_to_sales_q", "gross_margin_q", "operating_margin_q",
    "liabilities_to_assets_q", "retained_earnings_to_assets_q",
]
FUNDAMENTAL_TIMING_FIELDS = ["report_lag_days", "fundamental_age_days"]
INDUSTRY_FIELDS = ["gsector", "ggroup", "gind", "gsubind"]
EXPORTED_FUNDAMENTAL_FIELDS = (
    RAW_QUARTERLY_FIELDS + DERIVED_QUARTERLY_FIELDS
    + FUNDAMENTAL_TIMING_FIELDS + INDUSTRY_FIELDS
)

def _member(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return next(info.filename for info in archive.infolist() if not info.is_dir())

def inspect_wrds(wrds_root: str | Path) -> dict:
    root = Path(wrds_root)
    required = {
        "sp500_constituents_prices": SP500_REL,
        "sp500_daily_index": SP500_INDEX_REL,
        "ff3_momentum_daily": FF3_REL,
        "ff5_momentum_daily": FF5_REL,
        "fundamentals_quarterly": FUNDQ_REL,
        "permno_gvkey_link": LINK_REL,
        "kelly_153_zip": Path("Kelly_factor_153.parquet.zip"),
    }
    files = {
        name: {
            "path": str(root / relative),
            "exists": (root / relative).exists(),
            "size_gb": round((root / relative).stat().st_size / 1024**3, 3) if (root / relative).exists() else None,
        }
        for name, relative in required.items()
    }
    factor_ranges = {}
    for name, relative in (("ff3_mom", FF3_REL), ("ff5_mom", FF5_REL)):
        path = root / relative
        if path.exists():
            with zipfile.ZipFile(path) as archive:
                with archive.open(_member(path)) as stream:
                    frame = pd.read_csv(stream, usecols=["date"])
            dates = pd.to_datetime(frame["date"])
            factor_ranges[name] = {"start": str(dates.min().date()), "end": str(dates.max().date()), "rows": len(frame)}
    sample = root / "kelly_us_sample.parquet"
    kelly = {}
    if sample.exists():
        import pyarrow.parquet as pq
        metadata = pq.ParquetFile(sample)
        kelly = {
            "sample_rows": metadata.metadata.num_rows,
            "sample_columns": metadata.schema.names,
            "sample_column_count": len(metadata.schema.names),
        }
    return {
        "root": str(root),
        "ready": all(item["exists"] for name, item in files.items() if name != "kelly_153_zip"),
        "files": files,
        "factor_ranges": factor_ranges,
        "kelly": kelly,
        "notes": {
            "price_identity": "PERMNO",
            "fundamental_identity": "GVKEY linked to PERMNO with effective LINKDT/LINKENDDT",
            "membership": "Historical MbrStartDt/MbrEndDt; no present-day constituent backfill",
            "fundamental_timing": "Quarterly data must become usable on RDQ/publication date and is forward-filled only after that date",
        },
    }



def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def _load_point_in_time_fundamentals(root: Path, permnos: set[int], start_date: str, end_date: str) -> dict[int, pd.DataFrame]:
    source = root / FUNDQ_REL
    internal_fields = ["rdq", "cheq", "dlttq", "dlcq", "oibdpq", "cogsq"]
    columns = list(dict.fromkeys([
        "LPERMNO", "datadate", *internal_fields,
        *RAW_QUARTERLY_FIELDS, *INDUSTRY_FIELDS,
    ]))
    pieces = []
    with zipfile.ZipFile(source) as archive:
        member = next(info for info in archive.infolist() if not info.is_dir())
        with archive.open(member) as stream:
            for chunk in pd.read_csv(stream, usecols=columns, chunksize=250_000, low_memory=False):
                permno = pd.to_numeric(chunk["LPERMNO"], errors="coerce")
                chunk = chunk[permno.isin(permnos)].copy()
                if chunk.empty:
                    continue
                chunk["permno"] = pd.to_numeric(chunk["LPERMNO"], errors="coerce").astype(int)
                report = pd.to_datetime(chunk["datadate"], errors="coerce")
                release = pd.to_datetime(chunk["rdq"], errors="coerce").fillna(report + pd.Timedelta(days=90))
                chunk["datadate"] = report
                chunk["available_date"] = release
                chunk = chunk[(release >= pd.Timestamp(start_date) - pd.Timedelta(days=370))
                              & (release <= pd.Timestamp(end_date))]
                pieces.append(chunk)
    if not pieces:
        return {}

    frame = pd.concat(pieces, ignore_index=True)
    numeric = list(dict.fromkeys([
        "cheq", "dlttq", "dlcq", "oibdpq", "cogsq",
        *RAW_QUARTERLY_FIELDS, *INDUSTRY_FIELDS,
    ]))
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    frame = frame.sort_values(["permno", "datadate", "available_date"]).drop_duplicates(
        ["permno", "datadate"], keep="last"
    )
    grouped = frame.groupby("permno", sort=False)

    def lag4(column: str) -> pd.Series:
        return grouped[column].shift(4)

    def yoy(column: str) -> pd.Series:
        previous = lag4(column)
        return (frame[column] - previous) / previous.abs().replace(0, np.nan)

    frame["roa_q"] = _safe_ratio(frame["niq"], frame["atq"])
    frame["roe_q"] = _safe_ratio(frame["niq"], frame["ceqq"])
    frame["gross_profitability_q"] = _safe_ratio(frame["saleq"] - frame["cogsq"], frame["atq"])
    frame["operating_profitability_q"] = _safe_ratio(frame["oibdpq"], frame["atq"])
    frame["leverage_q"] = _safe_ratio(frame["dlttq"].fillna(0) + frame["dlcq"].fillna(0), frame["atq"])
    frame["cash_to_assets_q"] = _safe_ratio(frame["cheq"], frame["atq"])
    frame["asset_growth_q"] = yoy("atq")
    frame["sales_growth_q"] = yoy("saleq")
    frame["earnings_growth_q"] = yoy("niq")
    frame["operating_income_growth_q"] = yoy("oiadpq")
    average_assets = (frame["atq"] + lag4("atq")) / 2.0
    frame["inventory_change_to_assets_q"] = _safe_ratio(
        frame["invtq"] - lag4("invtq"), average_assets
    )
    frame["receivables_change_to_assets_q"] = _safe_ratio(
        frame["rectq"] - lag4("rectq"), average_assets
    )
    frame["ppent_change_to_assets_q"] = _safe_ratio(
        frame["ppentq"] - lag4("ppentq"), average_assets
    )
    frame["inventory_to_sales_q"] = _safe_ratio(frame["invtq"], frame["saleq"])
    frame["receivables_to_sales_q"] = _safe_ratio(frame["rectq"], frame["saleq"])
    frame["gross_margin_q"] = _safe_ratio(frame["saleq"] - frame["cogsq"], frame["saleq"])
    frame["operating_margin_q"] = _safe_ratio(frame["oiadpq"], frame["saleq"])
    frame["liabilities_to_assets_q"] = _safe_ratio(frame["ltq"], frame["atq"])
    frame["retained_earnings_to_assets_q"] = _safe_ratio(frame["req"], frame["atq"])
    frame["report_lag_days"] = (frame["available_date"] - frame["datadate"]).dt.days.astype(float)

    keep = [
        "available_date", "datadate",
        *RAW_QUARTERLY_FIELDS, *DERIVED_QUARTERLY_FIELDS,
        "report_lag_days", *INDUSTRY_FIELDS,
    ]
    frame = frame.replace([np.inf, -np.inf], np.nan)
    return {
        int(permno): group[keep].sort_values("available_date")
        for permno, group in frame.groupby("permno", sort=False)
    }


def build_sp500_qlib(
    wrds_root: str | Path,
    output_dir: str | Path,
    project_root: str | Path,
    start_date: str = "1980-01-01",
    end_date: str = "2025-12-31",
    chunk_size: int = 350_000,
) -> dict:
    root, output = Path(wrds_root), Path(output_dir)
    source = root / SP500_REL
    if not source.exists():
        raise FileNotFoundError(source)
    staging = output.parent / f"{output.name}_staging"
    binary_staging = output.parent / f"{output.name}_binary_staging"
    for temporary in (staging, binary_staging):
        if temporary.exists():
            shutil.rmtree(temporary)
    staging.mkdir(parents=True)
    from .delisting_returns import combine_return, load_delisting_returns
    delisting = load_delisting_returns(wrds_root)[["permno", "date", "delist_return"]]
    membership: set[tuple[str, str, str]] = set()
    fields = [
        "PERMNO", "MbrStartDt", "MbrEndDt", "DlyCalDt", "DlyOpen", "DlyHigh",
        "DlyLow", "DlyClose", "DlyPrc", "DlyVol", "DlyCumFacPr",
        "DlyCumFacShr", "DlyRet",
    ]
    with zipfile.ZipFile(source) as archive:
        member = next(info for info in archive.infolist() if not info.is_dir())
        with archive.open(member) as stream:
            for chunk in pd.read_csv(stream, usecols=fields, chunksize=chunk_size, low_memory=False):
                chunk["date"] = pd.to_datetime(chunk["DlyCalDt"], errors="coerce")
                chunk = chunk[(chunk["date"] >= start_date) & (chunk["date"] <= end_date)]
                chunk = chunk[pd.to_numeric(chunk["PERMNO"], errors="coerce").notna()]
                if chunk.empty:
                    continue
                chunk["symbol"] = "P" + chunk["PERMNO"].astype(int).astype(str)
                close = pd.to_numeric(chunk["DlyClose"], errors="coerce").fillna(pd.to_numeric(chunk["DlyPrc"], errors="coerce").abs())
                adjustment = pd.to_numeric(chunk["DlyCumFacPr"], errors="coerce").replace(0, np.nan).fillna(1.0)
                share_adjustment = pd.to_numeric(chunk["DlyCumFacShr"], errors="coerce").replace(0, np.nan).fillna(1.0)
                for source_name, target_name in (("DlyOpen", "open"), ("DlyHigh", "high"), ("DlyLow", "low")):
                    chunk[target_name] = pd.to_numeric(chunk[source_name], errors="coerce").fillna(close) / adjustment
                chunk["close"] = close / adjustment
                chunk["volume"] = pd.to_numeric(chunk["DlyVol"], errors="coerce").fillna(0).abs() * share_adjustment
                chunk["factor"] = 1.0
                chunk["change"] = pd.to_numeric(chunk["DlyRet"], errors="coerce")
                chunk["permno"] = pd.to_numeric(chunk["PERMNO"], errors="coerce")
                chunk = chunk.merge(delisting, on=["permno", "date"], how="left")
                chunk["ret_total"] = combine_return(chunk["change"], chunk["delist_return"])
                for symbol, group in chunk.groupby("symbol", sort=False):
                    path = staging / f"{symbol.lower()}.csv"
                    group[["date", "symbol", "open", "high", "low", "close", "volume", "factor", "change", "ret_total", "delist_return"]].to_csv(
                        path, mode="a", header=not path.exists(), index=False
                    )
                members = chunk[["symbol", "MbrStartDt", "MbrEndDt"]].drop_duplicates()
                membership.update(
                    (row.symbol, str(pd.Timestamp(row.MbrStartDt).date()), str(pd.Timestamp(row.MbrEndDt).date()))
                    for row in members.itertuples(index=False)
                    if pd.notna(row.MbrStartDt) and pd.notna(row.MbrEndDt)
                )
    permnos = {int(symbol[1:]) for symbol, _, _ in membership if symbol.startswith("P")}
    fundamentals = _load_point_in_time_fundamentals(root, permnos, start_date, end_date)
    fundamental_fields = list(EXPORTED_FUNDAMENTAL_FIELDS)
    for path in staging.glob("p*.csv"):
        permno = int(path.stem[1:])
        daily = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
        quarterly = fundamentals.get(permno)
        if quarterly is not None and not quarterly.empty:
            daily = pd.merge_asof(
                daily, quarterly.sort_values("available_date"),
                left_on="date", right_on="available_date",
                direction="backward", allow_exact_matches=True,
            )
            daily["fundamental_age_days"] = (
                daily["date"] - daily["available_date"]
            ).dt.days.astype(float)
            daily = daily.drop(columns=["available_date", "datadate"])
        for field in fundamental_fields:
            if field not in daily.columns:
                daily[field] = np.nan
        daily.to_csv(path, index=False)

    index_source = root / SP500_INDEX_REL
    with zipfile.ZipFile(index_source) as archive:
        member = next(info for info in archive.infolist() if not info.is_dir())
        with archive.open(member) as stream:
            index_frame = pd.read_csv(
                stream, usecols=["DlyCalDt", "DlyTotRet", "DlyTotInd"], low_memory=False
            )
    index_frame["date"] = pd.to_datetime(index_frame["DlyCalDt"], errors="coerce")
    index_frame = index_frame[
        (index_frame["date"] >= start_date) & (index_frame["date"] <= end_date)
    ].sort_values("date").drop_duplicates("date", keep="last")
    market_close = pd.to_numeric(index_frame["DlyTotInd"], errors="coerce")
    market_returns = pd.to_numeric(index_frame["DlyTotRet"], errors="coerce").fillna(0.0)
    benchmark_frame = pd.DataFrame({
        "date": index_frame["date"], "symbol": "^GSPC", "open": market_close,
        "high": market_close, "low": market_close, "close": market_close,
        "volume": 0.0, "factor": 1.0, "change": market_returns,
        "ret_total": market_returns, "delist_return": np.nan,
    })
    for field in fundamental_fields:
        benchmark_frame[field] = np.nan
    benchmark_frame.to_csv(staging / "^gspc.csv", index=False)
    dump_script = Path(project_root) / "tools" / "qlib-source" / "scripts" / "dump_bin.py"
    subprocess.run([
        sys.executable, str(dump_script), "dump_all", "--data_path", str(staging),
        "--qlib_dir", str(binary_staging), "--freq", "day", "--date_field_name", "date",
        "--file_suffix", ".csv", "--symbol_field_name", "symbol",
        "--include_fields", "open,high,low,close,volume,factor,change,ret_total,delist_return,"
        + ",".join(fundamental_fields),
    ], check=True)
    instruments = binary_staging / "instruments"
    instruments.mkdir(parents=True, exist_ok=True)
    lines = [f"{symbol}\t{start}\t{end}" for symbol, start, end in sorted(membership)]
    (instruments / "sp500.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    metadata = {
        "source": str(source), "built_at_utc": pd.Timestamp.utcnow().isoformat(),
        "start_date": start_date, "end_date": end_date,
        "membership_intervals": len(lines), "identity": "PERMNO",
        "fundamental_instruments": len(fundamentals),
        "fundamental_timing": "rdq; datadate+90d fallback; backward as-of only",
        "fundamental_fields": fundamental_fields,
    }
    (binary_staging / "wrds_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    backup = output.parent / f"{output.name}_previous"
    if backup.exists():
        shutil.rmtree(backup)
    if output.exists():
        output.rename(backup)
    binary_staging.rename(output)
    if backup.exists():
        shutil.rmtree(backup)
    shutil.rmtree(staging)
    return metadata

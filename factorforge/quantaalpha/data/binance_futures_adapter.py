"""Binance USD-M perpetual futures to Qlib daily data adapter.

Only public market-data endpoints are used; API credentials are not required.
The universe is point in time: on each day it holds the ``max_symbols``
USDT perpetuals with the highest trailing quote volume, measured only from
days before it. Candidates include delisted contracts: their daily klines and
funding come from the public archive at data.binance.vision when the live API
no longer serves them. Contracts never appear before their first trading day.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


BASE_URL = "https://fapi.binance.com"
ARCHIVE_URL = "https://data.binance.vision"
ARCHIVE_LIST_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
_S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trade_count", "taker_buy_volume",
    "taker_buy_quote_volume", "ignore",
]
# Point-in-time ranking: trailing mean quote volume over this many days,
# requiring at least VOLUME_MIN_DAYS observed days.
VOLUME_LOOKBACK_DAYS = 30
VOLUME_MIN_DAYS = 20
MARKET = "binance_usdm"
EXPORTED_FIELDS = [
    "open", "close", "high", "low", "volume", "factor", "return",
    "quote_volume", "trade_count", "taker_buy_volume",
    "taker_buy_quote_volume", "taker_buy_ratio", "funding_rate",
    "listing_age_days", "market_group",
]


def _get_bytes(url: str, retries: int = 5) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": "QuantaAlpha/2.0"})
            with urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as error:
            if error.code == 404:
                raise
            last_error = error
        except (URLError, TimeoutError) as error:
            last_error = error
        time.sleep(min(8.0, 0.75 * (2**attempt)))
    raise RuntimeError(f"Binance request failed: {url}: {last_error}")


def _json_get(path: str, params: dict | None = None, retries: int = 5):
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urlencode(params)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return json.loads(_get_bytes(url, retries=1).decode("utf-8"))
        except (HTTPError, RuntimeError, json.JSONDecodeError) as error:
            last_error = error
            if isinstance(error, HTTPError) and error.code in (400, 404):
                break
            time.sleep(min(8.0, 0.75 * (2**attempt)))
    raise RuntimeError(f"Binance public API request failed: {path}: {last_error}")


def _milliseconds(value: str | pd.Timestamp) -> int:
    stamp = pd.Timestamp(value, tz="UTC") if pd.Timestamp(value).tzinfo is None else pd.Timestamp(value).tz_convert("UTC")
    return int(stamp.timestamp() * 1000)


def _archive_list(prefix: str, delimiter: str | None = None) -> list[str]:
    """List archive keys (or sub-prefixes when ``delimiter`` is set) under ``prefix``."""
    output: list[str] = []
    marker = ""
    while True:
        params = {"prefix": prefix}
        if delimiter:
            params["delimiter"] = delimiter
        if marker:
            params["marker"] = marker
        root = ET.fromstring(_get_bytes(f"{ARCHIVE_LIST_URL}?{urlencode(params)}"))
        if delimiter:
            page = [item.text or "" for item in root.findall("s3:CommonPrefixes/s3:Prefix", _S3_NS)]
        else:
            page = [item.text or "" for item in root.findall("s3:Contents/s3:Key", _S3_NS)]
        output.extend(page)
        truncated = (root.findtext("s3:IsTruncated", default="false", namespaces=_S3_NS) or "").lower() == "true"
        if not truncated or not page:
            return output
        marker = root.findtext("s3:NextMarker", namespaces=_S3_NS) or page[-1]


def _is_usdt_perpetual_symbol(symbol: str) -> bool:
    # Dated delivery contracts carry an expiry suffix such as BTCUSDT_250328.
    return symbol.endswith("USDT") and "_" not in symbol


def _candidate_contracts(include_delisted: bool = True) -> tuple[list[dict], dict]:
    """Every USDT perpetual Binance has listed, whatever its status today.

    The live exchange list drops contracts some time after they delist, so
    archived symbols are added as well. Picking today's tradable contracts
    would leave only the survivors in every historical cross-section.
    """
    info = _json_get("/fapi/v1/exchangeInfo")
    contracts = {
        str(item["symbol"]).upper(): item for item in info.get("symbols", [])
        if item.get("contractType") == "PERPETUAL" and item.get("quoteAsset") == "USDT"
    }
    report = {
        "exchangeListed": len(contracts),
        "exchangeNotTrading": sum(1 for item in contracts.values() if item.get("status") != "TRADING"),
        "archiveOnly": 0,
        "archiveListing": "skipped",
    }
    if include_delisted:
        prefix = "data/futures/um/monthly/klines/"
        try:
            archived = {key[len(prefix):].strip("/").upper() for key in _archive_list(prefix, delimiter="/")}
            report["archiveListing"] = "ok"
        except Exception as error:  # the archive is optional; say so in the metadata
            archived = set()
            report["archiveListing"] = f"failed: {error}"
        for symbol in sorted(archived):
            if _is_usdt_perpetual_symbol(symbol) and symbol not in contracts:
                contracts[symbol] = {"symbol": symbol, "status": "DELISTED", "onboardDate": None}
                report["archiveOnly"] += 1
    return list(contracts.values()), report


def _read_archive_csv(key: str) -> pd.DataFrame:
    """One archived monthly CSV; newer files carry a header row, older ones do not."""
    with zipfile.ZipFile(io.BytesIO(_get_bytes(f"{ARCHIVE_URL}/{key}"))) as archive:
        with archive.open(archive.namelist()[0]) as handle:
            frame = pd.read_csv(handle, header=None, dtype=str)
    if not frame.empty and not str(frame.iat[0, 0]).strip().isdigit():
        frame = frame.iloc[1:]
    return frame.reset_index(drop=True)


def _months(start: pd.Timestamp, end: pd.Timestamp) -> set[str]:
    return {period.strftime("%Y-%m") for period in pd.period_range(start, end, freq="M")}


def _archive_klines(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> list[list]:
    wanted = _months(start, end)
    rows: list[list] = []
    for key in sorted(_archive_list(f"data/futures/um/monthly/klines/{symbol}/1d/")):
        if key.endswith(".zip") and key[-11:-4] in wanted:
            frame = _read_archive_csv(key)
            rows.extend(frame.iloc[:, :len(KLINE_COLUMNS)].values.tolist())
    return rows


def _archive_funding(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    wanted = _months(start, end)
    parts = []
    for key in sorted(_archive_list(f"data/futures/um/monthly/fundingRate/{symbol}/")):
        if key.endswith(".zip") and key[-11:-4] in wanted:
            frame = _read_archive_csv(key)
            # calc_time, funding_interval_hours, last_funding_rate
            parts.append(pd.DataFrame({"fundingTime": frame.iloc[:, 0], "fundingRate": frame.iloc[:, -1]}))
    if not parts:
        return pd.Series(dtype=float)
    return _daily_funding(pd.concat(parts, ignore_index=True))


def _daily_funding(frame: pd.DataFrame) -> pd.Series:
    frame = frame.copy()
    frame["date"] = pd.to_datetime(pd.to_numeric(frame["fundingTime"], errors="coerce"), unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    frame["fundingRate"] = pd.to_numeric(frame["fundingRate"], errors="coerce")
    return frame.dropna(subset=["date"]).groupby("date")["fundingRate"].sum(min_count=1)


def point_in_time_membership(
    frames: dict[str, pd.DataFrame],
    max_symbols: int,
    lookback_days: int = VOLUME_LOOKBACK_DAYS,
    min_days: int = VOLUME_MIN_DAYS,
) -> list[tuple[str, str, str]]:
    """Qlib membership spans: each day's top ``max_symbols`` by trailing quote volume.

    The ranking on day t uses quote volume up to day t-1 only, so a contract
    enters the universe from volume it has already traded and leaves it once
    its volume fades or it stops trading.
    """
    volume = pd.DataFrame({
        symbol: frame.set_index("date")["quote_volume"].astype(float)
        for symbol, frame in frames.items() if not frame.empty
    }).sort_index()
    if volume.empty:
        return []
    calendar = pd.date_range(volume.index.min(), volume.index.max(), freq="D")
    volume = volume.reindex(calendar)
    trailing = volume.rolling(lookback_days, min_periods=min_days).mean().shift(1)
    # A contract can only be a member on days it actually traded.
    trailing = trailing.where(volume.notna())
    ranks = trailing.rank(axis=1, ascending=False, method="first")
    member = (ranks <= int(max_symbols)).to_numpy()
    spans: list[tuple[str, str, str]] = []
    for column, symbol in enumerate(volume.columns):
        flags = member[:, column]
        if not flags.any():
            continue
        edges = np.diff(np.concatenate([[0], flags.astype(np.int8), [0]]))
        for begin, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1):
            spans.append((symbol, str(calendar[begin].date()), str(calendar[stop].date())))
    return sorted(spans)


def _paged_klines(symbol: str, start_ms: int, end_ms: int) -> list[list]:
    output: list[list] = []
    cursor = start_ms
    one_day_ms = 86_400_000
    while cursor <= end_ms:
        batch = _json_get("/fapi/v1/klines", {
            "symbol": symbol, "interval": "1d", "startTime": cursor,
            "endTime": end_ms, "limit": 1500,
        })
        if not batch:
            break
        output.extend(batch)
        next_cursor = int(batch[-1][0]) + one_day_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(0.03)
    return output


def _paged_funding(symbol: str, start_ms: int, end_ms: int) -> pd.Series:
    records: list[dict] = []
    cursor = start_ms
    while cursor <= end_ms:
        batch = _json_get("/fapi/v1/fundingRate", {
            "symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": 1000,
        })
        if not batch:
            break
        records.extend(batch)
        next_cursor = int(batch[-1]["fundingTime"]) + 1
        if next_cursor <= cursor or len(batch) < 1000:
            break
        cursor = next_cursor
        time.sleep(0.03)
    if not records:
        return pd.Series(dtype=float)
    return _daily_funding(pd.DataFrame(records))


def _symbol_frame(meta: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """Daily bars for one contract: live API first, public archive for delisted ones."""
    symbol = str(meta["symbol"]).upper()
    onboard_ms = int(meta.get("onboardDate") or 0)
    onboard = (
        pd.to_datetime(onboard_ms, unit="ms", utc=True).tz_localize(None).normalize()
        if onboard_ms else None
    )
    start = max(pd.Timestamp(start_date), onboard) if onboard is not None else pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    if start > end:
        return pd.DataFrame()
    start_ms, end_ms = _milliseconds(start), _milliseconds(end + pd.Timedelta(days=1)) - 1
    rows: list[list] = []
    funding = pd.Series(dtype=float)
    source = "api"
    try:
        rows = _paged_klines(symbol, start_ms, end_ms)
        if rows:
            funding = _paged_funding(symbol, start_ms, end_ms)
    except RuntimeError:
        rows = []
    if not rows and meta.get("status") != "TRADING":
        source = "archive"
        rows = _archive_klines(symbol, start, end)
        funding = _archive_funding(symbol, start, end) if rows else funding
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame([row[:len(KLINE_COLUMNS)] for row in rows], columns=KLINE_COLUMNS)
    frame["date"] = pd.to_datetime(pd.to_numeric(frame["open_time"], errors="coerce"), unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    frame = frame.dropna(subset=["date"]).drop_duplicates("date", keep="last").sort_values("date")
    frame = frame[(frame["date"] >= start) & (frame["date"] <= end)].reset_index(drop=True)
    if frame.empty:
        return pd.DataFrame()
    numeric = [
        "open", "high", "low", "close", "volume", "quote_volume", "trade_count",
        "taker_buy_volume", "taker_buy_quote_volume",
    ]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    listed = onboard if onboard is not None else frame["date"].min()
    frame["factor"] = 1.0
    frame["return"] = frame["close"].pct_change()
    frame["taker_buy_ratio"] = frame["taker_buy_quote_volume"] / frame["quote_volume"].replace(0, np.nan)
    frame["funding_rate"] = frame["date"].map(funding).fillna(0.0)
    frame["listing_age_days"] = (frame["date"] - listed).dt.days.astype(float)
    frame["market_group"] = 1.0
    frame["symbol"] = symbol
    frame.attrs["source"] = source
    return frame[["date", "symbol", *EXPORTED_FIELDS]].replace([np.inf, -np.inf], np.nan)


def inspect_binance_qlib(output_dir: str | Path) -> dict:
    output = Path(output_dir)
    calendar = output / "calendars" / "day.txt"
    instruments = output / "instruments" / f"{MARKET}.txt"
    lines = instruments.read_text(encoding="utf-8").splitlines() if instruments.exists() else []
    dates = calendar.read_text(encoding="utf-8").splitlines() if calendar.exists() else []
    return {
        "exchange": "Binance",
        "market": "USD-M USDT perpetual futures",
        "publicApi": BASE_URL,
        "built": calendar.exists() and instruments.exists() and bool(lines),
        "qlibPath": str(output),
        "symbols": len({line.split("\t")[0] for line in lines if line.strip()}),
        "membershipSpans": len(lines),
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "fields": EXPORTED_FIELDS,
        "universeNote": (
            "Point-in-time: each day's top contracts by trailing quote volume known "
            "before that day; delisted contracts included where Binance still serves "
            "or archives their history."
        ),
    }


def funding_sensitivity(signal: pd.Series, funding_rate: pd.Series, quantile: float = 0.1) -> dict[str, float]:
    """Diagnostic funding exposure of a cross-sectional long-short signal."""
    frame = pd.concat([signal.rename("signal"), funding_rate.rename("funding")], axis=1).dropna()
    daily_corr: list[float] = []
    daily_spread: list[float] = []

    # Qlib normally names the time level ``datetime``, but calculated factor
    # frames can preserve it as ``date`` or leave it unnamed.  Group by the
    # actual datetime-like level instead of assuming one fixed label.
    index = frame.index
    if isinstance(index, pd.MultiIndex):
        level_position = next(
            (
                position
                for position, name in enumerate(index.names)
                if name and ("date" in str(name).lower() or "time" in str(name).lower())
            ),
            None,
        )
        if level_position is None:
            level_position = next(
                (
                    position
                    for position in range(index.nlevels)
                    if pd.api.types.is_datetime64_any_dtype(index.get_level_values(position).dtype)
                ),
                0,
            )
        session_key = index.get_level_values(level_position)
    else:
        session_key = index

    for _, cross_section in frame.groupby(session_key):
        if len(cross_section) < 3 or cross_section["signal"].nunique() < 2:
            continue
        corr = cross_section["signal"].corr(cross_section["funding"], method="spearman")
        if np.isfinite(corr):
            daily_corr.append(float(corr))
        count = max(1, int(np.floor(len(cross_section) * quantile)))
        ordered = cross_section.sort_values("signal")
        spread = ordered.iloc[-count:]["funding"].mean() - ordered.iloc[:count]["funding"].mean()
        if np.isfinite(spread):
            daily_spread.append(float(spread))
    mean_spread = float(np.mean(daily_spread)) if daily_spread else np.nan
    return {
        "crypto.funding_signal_rank_corr": float(np.mean(daily_corr)) if daily_corr else np.nan,
        "crypto.long_short_daily_funding_spread": mean_spread,
        # Positive funding is paid by longs and received by shorts.
        "crypto.long_short_funding_pnl_annualized": -365.0 * mean_spread if np.isfinite(mean_spread) else np.nan,
        "crypto.funding_observations": float(len(daily_spread)),
    }


def build_binance_usdm_qlib(
    output_dir: str | Path,
    project_root: str | Path,
    start_date: str = "2020-01-01",
    end_date: str | None = None,
    max_symbols: int = 100,
    include_delisted: bool = True,
    max_candidates: int | None = None,
) -> dict:
    """Build the Qlib store; ``max_symbols`` is the universe size on each day."""
    output = Path(output_dir)
    end_date = end_date or datetime.now(timezone.utc).date().isoformat()
    csv_staging = output.parent / f"{output.name}_csv_staging"
    bin_staging = output.parent / f"{output.name}_binary_staging"
    for path in (csv_staging, bin_staging):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)

    candidates, candidate_report = _candidate_contracts(include_delisted)
    if max_candidates:
        candidates = candidates[:int(max_candidates)]
    frames: dict[str, pd.DataFrame] = {}
    full_ranges: list[tuple[str, str, str]] = []
    failures: dict[str, str] = {}
    archived_used = 0
    for index, meta in enumerate(candidates, 1):
        symbol = str(meta["symbol"]).upper()
        try:
            frame = _symbol_frame(meta, start_date, end_date)
            if frame.empty:
                continue
            frame.to_csv(csv_staging / f"{symbol}.csv", index=False)
            archived_used += frame.attrs.get("source") == "archive"
            frames[symbol] = frame[["date", "quote_volume"]]
            full_ranges.append((symbol, str(frame["date"].min().date()), str(frame["date"].max().date())))
            print(f"[{index}/{len(candidates)}] {symbol}: {len(frame)} daily rows", flush=True)
        except Exception as error:  # keep a large build useful if one contract is malformed
            failures[symbol] = str(error)
            print(f"[{index}/{len(candidates)}] {symbol}: FAILED: {error}", flush=True)
    membership = point_in_time_membership(frames, max(2, int(max_symbols)))

    if len(full_ranges) < 2 or not membership:
        raise RuntimeError(f"Binance build produced too few usable contracts: {failures}")
    dump_script = Path(project_root) / "tools" / "qlib-source" / "scripts" / "dump_bin.py"
    command = [
        sys.executable, str(dump_script), "dump_all", "--data_path", str(csv_staging),
        "--qlib_dir", str(bin_staging), "--freq", "day", "--date_field_name", "date",
        "--symbol_field_name", "symbol", "--exclude_fields", "date,symbol",
    ]
    subprocess.run(command, check=True)
    instruments_dir = bin_staging / "instruments"
    instruments_dir.mkdir(parents=True, exist_ok=True)
    # binance_usdm: dated point-in-time membership. all: every contract's full history.
    (instruments_dir / f"{MARKET}.txt").write_text(
        "\n".join("\t".join(item) for item in membership) + "\n", encoding="utf-8")
    (instruments_dir / "all.txt").write_text(
        "\n".join("\t".join(item) for item in sorted(full_ranges)) + "\n", encoding="utf-8")
    delisted_complete = include_delisted and candidate_report["archiveListing"] == "ok"
    metadata = {
        "builtAt": datetime.now(timezone.utc).isoformat(), "source": BASE_URL,
        "archive": ARCHIVE_URL if include_delisted else None,
        "market": MARKET, "maxSymbols": max_symbols,
        "universe": (
            f"point_in_time_top_{max_symbols}_by_trailing_{VOLUME_LOOKBACK_DAYS}d_quote_volume"
        ),
        "symbols": len(full_ranges), "membershipSpans": len(membership),
        "candidates": candidate_report, "archivedContractsUsed": int(archived_used),
        "startDate": start_date, "endDate": end_date, "failures": failures,
        "survivorshipWarning": (
            None if delisted_complete else
            "Delisted contracts could not be listed from the archive; the universe "
            "may still miss contracts Binance no longer serves."
        ),
    }
    (bin_staging / "binance_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if output.exists():
        backup = output.parent / f"{output.name}_previous"
        if backup.exists():
            shutil.rmtree(backup)
        output.replace(backup)
        bin_staging.replace(output)
        shutil.rmtree(backup)
    else:
        bin_staging.replace(output)
    shutil.rmtree(csv_staging, ignore_errors=True)
    return {**inspect_binance_qlib(output), "failures": failures}

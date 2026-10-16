"""Binance USD-M perpetual futures to Qlib daily data adapter.

Only public market-data endpoints are used; API credentials are not required.
The universe is a point-in-time snapshot of currently trading USDT perpetuals,
ranked by 24-hour quote volume.  ``onboardDate`` is respected so contracts do
not appear before listing.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


BASE_URL = "https://fapi.binance.com"
MARKET = "binance_usdm"
EXPORTED_FIELDS = [
    "open", "close", "high", "low", "volume", "factor", "return",
    "quote_volume", "trade_count", "taker_buy_volume",
    "taker_buy_quote_volume", "taker_buy_ratio", "funding_rate",
    "listing_age_days", "market_group",
]


def _json_get(path: str, params: dict | None = None, retries: int = 5):
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urlencode(params)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": "QuantaAlpha/2.0"})
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(min(8.0, 0.75 * (2**attempt)))
    raise RuntimeError(f"Binance public API request failed: {path}: {last_error}")


def _milliseconds(value: str | pd.Timestamp) -> int:
    stamp = pd.Timestamp(value, tz="UTC") if pd.Timestamp(value).tzinfo is None else pd.Timestamp(value).tz_convert("UTC")
    return int(stamp.timestamp() * 1000)


def _exchange_universe(max_symbols: int) -> list[dict]:
    info = _json_get("/fapi/v1/exchangeInfo")
    tickers = _json_get("/fapi/v1/ticker/24hr")
    quote_volume = {
        item.get("symbol"): float(item.get("quoteVolume") or 0)
        for item in tickers if isinstance(item, dict)
    }
    rows = [
        item for item in info.get("symbols", [])
        if item.get("contractType") == "PERPETUAL"
        and item.get("quoteAsset") == "USDT"
        and item.get("status") == "TRADING"
    ]
    rows.sort(key=lambda item: quote_volume.get(item.get("symbol"), 0.0), reverse=True)
    return rows[:max(2, int(max_symbols))]


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
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    frame["fundingRate"] = pd.to_numeric(frame["fundingRate"], errors="coerce")
    return frame.groupby("date")["fundingRate"].sum(min_count=1)


def _symbol_frame(meta: dict, start_date: str, end_date: str) -> pd.DataFrame:
    symbol = str(meta["symbol"]).upper()
    onboard = pd.to_datetime(int(meta.get("onboardDate") or 0), unit="ms", utc=True).tz_localize(None).normalize()
    start = max(pd.Timestamp(start_date), onboard)
    end = pd.Timestamp(end_date)
    if start > end:
        return pd.DataFrame()
    rows = _paged_klines(symbol, _milliseconds(start), _milliseconds(end + pd.Timedelta(days=1)) - 1)
    if not rows:
        return pd.DataFrame()
    columns = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trade_count", "taker_buy_volume",
        "taker_buy_quote_volume", "ignore",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    frame["date"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    numeric = [
        "open", "high", "low", "close", "volume", "quote_volume", "trade_count",
        "taker_buy_volume", "taker_buy_quote_volume",
    ]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    frame["factor"] = 1.0
    frame["return"] = frame["close"].pct_change()
    frame["taker_buy_ratio"] = frame["taker_buy_quote_volume"] / frame["quote_volume"].replace(0, np.nan)
    funding = _paged_funding(symbol, _milliseconds(start), _milliseconds(end + pd.Timedelta(days=1)) - 1)
    frame["funding_rate"] = frame["date"].map(funding).fillna(0.0)
    frame["listing_age_days"] = (frame["date"] - onboard).dt.days.astype(float)
    frame["market_group"] = 1.0
    frame["symbol"] = symbol
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
        "symbols": len(lines),
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "fields": EXPORTED_FIELDS,
        "universeNote": "Current trading USDT perpetual snapshot; onboard dates are respected.",
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
) -> dict:
    output = Path(output_dir)
    end_date = end_date or datetime.now(timezone.utc).date().isoformat()
    csv_staging = output.parent / f"{output.name}_csv_staging"
    bin_staging = output.parent / f"{output.name}_binary_staging"
    for path in (csv_staging, bin_staging):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)

    universe = _exchange_universe(max_symbols)
    membership: list[tuple[str, str, str]] = []
    failures: dict[str, str] = {}
    for index, meta in enumerate(universe, 1):
        symbol = str(meta["symbol"]).upper()
        try:
            frame = _symbol_frame(meta, start_date, end_date)
            if frame.empty:
                continue
            frame.to_csv(csv_staging / f"{symbol}.csv", index=False)
            membership.append((symbol, str(frame["date"].min().date()), str(frame["date"].max().date())))
            print(f"[{index}/{len(universe)}] {symbol}: {len(frame)} daily rows", flush=True)
        except Exception as error:  # keep a large build useful if one new contract is malformed
            failures[symbol] = str(error)
            print(f"[{index}/{len(universe)}] {symbol}: FAILED: {error}", flush=True)

    if len(membership) < 2:
        raise RuntimeError(f"Binance build produced too few usable contracts: {failures}")
    dump_script = Path(project_root) / "tools" / "qlib-source" / "scripts" / "dump_bin.py"
    command = [
        sys.executable, str(dump_script), "dump_all", "--data_path", str(csv_staging),
        "--qlib_dir", str(bin_staging), "--freq", "day", "--date_field_name", "date",
        "--symbol_field_name", "symbol", "--exclude_fields", "date,symbol",
    ]
    subprocess.run(command, check=True)
    instrument_text = "\n".join("\t".join(item) for item in sorted(membership)) + "\n"
    instruments_dir = bin_staging / "instruments"
    instruments_dir.mkdir(parents=True, exist_ok=True)
    (instruments_dir / f"{MARKET}.txt").write_text(instrument_text, encoding="utf-8")
    (instruments_dir / "all.txt").write_text(instrument_text, encoding="utf-8")
    metadata = {
        "builtAt": datetime.now(timezone.utc).isoformat(), "source": BASE_URL,
        "market": MARKET, "maxSymbols": max_symbols, "symbols": len(membership),
        "startDate": start_date, "endDate": end_date, "failures": failures,
        "survivorshipWarning": "Universe is the current trading-contract snapshot; delisted contracts are not backfilled.",
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

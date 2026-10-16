"""China-specific Barra diagnostics and locally derived FF-style factors."""
from __future__ import annotations

import numpy as np
import pandas as pd

from quantaalpha.backtest.asset_pricing import regress_with_factor_frame


_MARKET_CACHE: dict[tuple[str, str, str], pd.DataFrame] = {}
_FACTOR_CACHE: dict[tuple[str, str, str], pd.DataFrame] = {}

RAW_FIELDS = [
    "$close", "$total_mv", "$turnover_rate_f", "$pb", "$pe_ttm", "$roe",
    "$debt_to_assets", "$assets_yoy",
]


def _market_frame(instruments, start: str, end: str) -> pd.DataFrame:
    from qlib.data import D
    key = (str(instruments), str(start), str(end))
    if key in _MARKET_CACHE:
        return _MARKET_CACHE[key].copy()
    warmup = str((pd.Timestamp(start) - pd.Timedelta(days=430)).date())
    frame = D.features(instruments, RAW_FIELDS, start_time=warmup, end_time=end, freq="day")
    frame.columns = [field[1:] for field in RAW_FIELDS]
    frame = frame.replace([np.inf, -np.inf], np.nan).sort_index()
    close = frame["close"].groupby(level="instrument")
    frame["return"] = close.pct_change()
    frame["momentum"] = close.shift(21) / close.shift(252) - 1
    frame["residual_volatility"] = frame["return"].groupby(level="instrument").rolling(60).std().droplevel(0)
    market_return = frame["return"].groupby(level="datetime").mean().rename("market_return")
    frame = frame.join(market_return, on="datetime")
    def rolling_beta(group):
        covariance = group["return"].rolling(252, min_periods=120).cov(group["market_return"])
        variance = group["market_return"].rolling(252, min_periods=120).var().replace(0, np.nan)
        return covariance / variance
    frame["beta"] = frame.groupby(level="instrument", group_keys=False).apply(rolling_beta)
    frame["size"] = np.log(frame["total_mv"].clip(lower=1))
    frame["value"] = 1.0 / frame["pb"].where(frame["pb"] > 0)
    frame["earnings_yield"] = 1.0 / frame["pe_ttm"].where(frame["pe_ttm"] > 0)
    frame["liquidity"] = np.log1p(frame["turnover_rate_f"].clip(lower=0))
    frame["profitability"] = frame["roe"]
    frame["leverage"] = frame["debt_to_assets"]
    frame["growth"] = frame["assets_yoy"]
    dates = frame.index.get_level_values("datetime")
    result = frame[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    _MARKET_CACHE[key] = result
    return result.copy()


def calculate_barra_style_exposures(signal, instruments, start: str, end: str) -> dict[str, float]:
    """Cross-sectional factor exposure to practical China Barra-style descriptors."""
    market = _market_frame(instruments, start, end)
    score = signal.rename("signal") if isinstance(signal, pd.Series) else signal.iloc[:, 0].rename("signal")
    joined = pd.concat([score, market], axis=1, join="inner")
    styles = ["beta", "size", "value", "earnings_yield", "momentum", "residual_volatility",
              "liquidity", "profitability", "leverage", "growth"]
    output: dict[str, float] = {}
    for style in styles:
        sample = joined[["signal", style]].dropna()
        if sample.empty:
            continue
        daily_corr = sample.groupby(level="datetime").apply(lambda x: x["signal"].corr(x[style]))
        output[f"barra.{style}.mean_correlation"] = float(daily_corr.mean())
        output[f"barra.{style}.mean_abs_correlation"] = float(daily_corr.abs().mean())
        output[f"barra.{style}.coverage"] = float(len(sample) / max(joined["signal"].notna().sum(), 1))
    return output


def _weighted_return(frame: pd.DataFrame) -> float:
    valid = frame[["return", "total_mv"]].dropna()
    if valid.empty:
        return np.nan
    weights = valid["total_mv"].clip(lower=0)
    if weights.sum() <= 0:
        return float(valid["return"].mean())
    return float(np.average(valid["return"], weights=weights))


def _spread(group: pd.DataFrame, column: str, high_minus_low: bool = True) -> float:
    valid = group[[column, "return", "total_mv"]].dropna()
    if len(valid) < 30:
        return np.nan
    low, high = valid[column].quantile([0.3, 0.7])
    lo = _weighted_return(valid.loc[valid[column] <= low])
    hi = _weighted_return(valid.loc[valid[column] >= high])
    return float(hi - lo if high_minus_low else lo - hi)


def derive_china_factor_returns(instruments, start: str, end: str) -> pd.DataFrame:
    """Derive investable daily CN FF3/FF5/Mom proxies from point-in-time local data."""
    key = (str(instruments), str(start), str(end))
    if key in _FACTOR_CACHE:
        return _FACTOR_CACHE[key].copy()
    frame = _market_frame(instruments, start, end).reset_index()
    frame["month"] = frame["datetime"].dt.to_period("M")
    month_end = frame.sort_values("datetime").groupby(["month", "instrument"], observed=True).tail(1)
    descriptors = month_end[["month", "instrument", "size", "value", "profitability", "growth", "momentum"]].copy()
    descriptors["month"] = descriptors["month"] + 1  # information becomes tradable next month
    daily = frame.merge(descriptors, on=["month", "instrument"], suffixes=("", "_sort"), how="left")
    factors = []
    for date, group in daily.groupby("datetime", sort=True):
        value = {
            "date": date,
            "mktrf": _weighted_return(group),
            "smb": -_spread(group.rename(columns={"size_sort": "sort_value"}), "sort_value"),
            "hml": _spread(group.rename(columns={"value_sort": "sort_value"}), "sort_value"),
            "rmw": _spread(group.rename(columns={"profitability_sort": "sort_value"}), "sort_value"),
            "cma": _spread(group.rename(columns={"growth_sort": "sort_value"}), "sort_value", high_minus_low=False),
            "umd": _spread(group.rename(columns={"momentum_sort": "sort_value"}), "sort_value"),
        }
        factors.append(value)
    result = pd.DataFrame(factors).set_index("date").sort_index()
    _FACTOR_CACHE[key] = result
    return result.copy()


def regress_china_asset_pricing(portfolio_returns, instruments, start: str, end: str):
    factors = derive_china_factor_returns(instruments, start, end)
    return regress_with_factor_frame(portfolio_returns, factors)

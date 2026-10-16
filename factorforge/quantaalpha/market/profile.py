"""Runtime market profile shared by mining and post-mining evaluation."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketProfile:
    mode: str
    region: str
    instrument: str
    name: str
    classification_fields: tuple[str, ...]
    primary_classification: str
    robustness_classification: str

    @property
    def qlib_classification_fields(self) -> list[str]:
        return [f"${field}" for field in self.classification_fields]


def get_market_profile(environment: dict[str, str] | None = None) -> MarketProfile:
    env = os.environ if environment is None else environment
    mode = str(env.get("MARKET_MODE", "us")).strip().lower()
    default_market = "csi300" if mode == "cn" else ("binance_usdm" if mode == "crypto" else "sp500")
    market = str(env.get("QLIB_MARKET", default_market)).strip().lower()
    if mode == "crypto":
        return MarketProfile(
            mode="crypto", region="us", instrument="binance_usdm",
            name="Binance USD-M Perpetual",
            # One synthetic group makes the existing industry-aware evaluator
            # perform whole-market demeaning/ranking without inventing sectors.
            classification_fields=("market_group",),
            primary_classification="market_group",
            robustness_classification="market_group",
        )
    if mode == "cn":
        allowed = {"csi300", "csi500", "sme_composite"}
        if market not in allowed:
            market = "csi300"
        names = {"csi300": "沪深300", "csi500": "中证500", "sme_composite": "中小综指"}
        return MarketProfile(
            mode="cn", region="cn", instrument=market, name=names[market],
            classification_fields=("sw_l1", "sw_l2", "sw_l3"),
            primary_classification="sw_l1", robustness_classification="sw_l2",
        )
    return MarketProfile(
        mode="us", region="us", instrument="sp500", name="S&P 500",
        classification_fields=("gsector", "ggroup", "gind", "gsubind"),
        primary_classification="gsector", robustness_classification="ggroup",
    )


def qlib_region(profile: MarketProfile):
    from qlib.constant import REG_CN, REG_US
    return REG_CN if profile.region == "cn" else REG_US


def eligibility_fields(profile: MarketProfile) -> list[str]:
    if profile.mode == "cn":
        return ["$is_st", "$listing_age_days"]
    if profile.mode == "crypto":
        return ["$listing_age_days", "$funding_rate"]
    return []


def apply_market_eligibility(signal, frame, environment: dict[str, str] | None = None):
    """Apply date-aware A-share filters without changing the stored universe."""
    if frame is None or frame.empty:
        return signal
    env = os.environ if environment is None else environment
    result = signal.copy()
    # Qlib may return panels as (instrument, datetime), while generated factor
    # files use (datetime, instrument). Reindexing without canonicalizing the
    # level order silently turns every eligibility value into NaN.
    def canonicalize(obj):
        if not isinstance(obj.index, pd.MultiIndex) or obj.index.nlevels < 2:
            return obj
        names = list(obj.index.names)
        datetime_level = names.index("datetime") if "datetime" in names else 0
        instrument_level = names.index("instrument") if "instrument" in names else 1
        normalized = obj.copy()
        normalized.index = pd.MultiIndex.from_arrays(
            [
                pd.to_datetime(obj.index.get_level_values(datetime_level), errors="coerce"),
                obj.index.get_level_values(instrument_level).astype(str).str.upper(),
            ],
            names=["datetime", "instrument"],
        )
        return normalized[~normalized.index.duplicated(keep="last")].sort_index()

    result = canonicalize(result)
    frame = canonicalize(frame)
    if profile := get_market_profile(env):
        if profile.mode == "crypto" and "listing_age_days" in frame:
            minimum = float(env.get("CRYPTO_MIN_LISTING_DAYS", "90"))
            result = result.where(frame["listing_age_days"].reindex(result.index) >= minimum)
    if str(env.get("CN_EXCLUDE_ST", "true")).lower() in {"1", "true", "yes", "on"} and "is_st" in frame:
        result = result.where(frame["is_st"].reindex(result.index).fillna(0) < 0.5)
    if str(env.get("CN_EXCLUDE_NEW_STOCKS", "true")).lower() in {"1", "true", "yes", "on"} and "listing_age_days" in frame:
        minimum = float(env.get("CN_NEW_STOCK_MIN_TRADING_DAYS", "375"))
        result = result.where(frame["listing_age_days"].reindex(result.index) >= minimum)
    instruments = result.index.get_level_values("instrument").astype(str).str.upper()
    board_rules = (
        ("CN_EXCLUDE_CHINEXT", instruments.str.match(r"SZ30[01]")),
        ("CN_EXCLUDE_STAR", instruments.str.startswith("SH688")),
        ("CN_EXCLUDE_BSE", instruments.str.startswith("BJ")),
    )
    for key, board_mask in board_rules:
        if str(env.get(key, "false")).lower() in {"1", "true", "yes", "on"}:
            result = result.where(~np.asarray(board_mask))
    return result

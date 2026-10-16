"""On-demand single-factor evaluation for train/validation/test splits.

The mining loop only uses validation results.  This module is called by the
factor-detail API after mining, so held-out test statistics cannot influence
LLM feedback or evolution selection.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantaalpha.backtest.asset_pricing import flatten_asset_pricing, regress_asset_pricing
from quantaalpha.backtest.long_short_analytics import calculate_industry_aware_analytics


SPLIT_ENV = {
    "train": ("TRAIN_START_DATE", "TRAIN_END_DATE"),
    "valid": ("VALID_START_DATE", "VALID_END_DATE"),
    "test": ("TEST_START_DATE", "TEST_END_DATE"),
}


def _normalize_signal(value: Any) -> pd.Series:
    signal = value if isinstance(value, pd.Series) else value.iloc[:, 0]
    if not isinstance(signal.index, pd.MultiIndex):
        raise ValueError("因子信号缓存缺少 datetime/instrument 双层索引")
    names = list(signal.index.names)
    date_level = names.index("datetime") if "datetime" in names else 0
    instrument_level = names.index("instrument") if "instrument" in names else 1
    signal = signal.copy()
    signal.index = pd.MultiIndex.from_arrays(
        [
            pd.to_datetime(signal.index.get_level_values(date_level)),
            signal.index.get_level_values(instrument_level).astype(str),
        ],
        names=["datetime", "instrument"],
    )
    return signal.replace([np.inf, -np.inf], np.nan).sort_index()


def _calculate_signal_from_expression(
    factor: dict[str, Any],
    project_root: Path,
    environment: dict[str, str],
) -> pd.Series:
    """Rebuild a missing/stale cache from the stored factor expression."""
    from qlib.data import D
    from quantaalpha.backtest.custom_factor_calculator import CustomFactorCalculator

    expression = str(factor.get("factor_expression", "")).strip()
    factor_name = str(factor.get("factor_name") or factor.get("factor_id") or "factor")
    if not expression:
        raise ValueError("因子没有保存表达式，无法自动重算")
    symbols = sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)))
    qlib_fields = [symbol for symbol in symbols if symbol != "$return"]
    # CustomFactorCalculator always derives $return during data preparation,
    # including for a purely fundamental formula, so $close is mandatory.
    if "$close" not in qlib_fields:
        qlib_fields.append("$close")
    if not qlib_fields:
        qlib_fields = ["$close"]

    start = environment.get("TRAIN_START_DATE") or "1987-01-01"
    end = environment.get("TEST_END_DATE") or environment.get("VALID_END_DATE") or "2025-12-31"
    try:
        from quantaalpha.market.profile import get_market_profile
        profile = get_market_profile(environment)
        raw = D.features(
            D.instruments(profile.instrument),
            qlib_fields,
            start_time=start,
            end_time=end,
            freq="day",
        )
    except Exception as exc:
        raise ValueError(
            f"公式所需基础字段无法读取（{', '.join(qlib_fields)}）：{exc}"
        ) from exc
    if raw.empty:
        raise ValueError("公式所需基础数据为空，无法自动重算")
    raw.columns = qlib_fields
    if "$return" in symbols:
        raw["$return"] = raw.groupby(level="instrument")["$close"].transform(
            lambda values: values / values.shift(1) - 1
        )

    cache_dir = project_root / "data" / "results" / "factor_cache"
    config = {
        "data": {
            "provider_uri": environment.get("QLIB_DATA_DIR") or environment.get("WRDS_QLIB_DATA_DIR"),
            "region": profile.region,
            "market": profile.instrument,
            "start_time": start,
            "end_time": end,
        },
        "dataset": {"segments": {"test": [environment.get("TEST_START_DATE"), end]}},
        "factor_calculation": {"factor_timeout": 600},
    }
    calculator = CustomFactorCalculator(
        data_df=raw,
        cache_dir=cache_dir,
        auto_extract_cache=False,
        config=config,
    )
    result = calculator.calculate_factor(factor_name, expression)
    if result is None or result.dropna().empty:
        raise ValueError("因子公式解析或计算失败，未产生任何有限值")
    result = _normalize_signal(result)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # The expression-only key is the stable factor-library cache used by
    # split evaluation, correlation heatmaps and cleanup reference tracking.
    stable_cache = cache_dir / f"{hashlib.md5(expression.encode()).hexdigest()}.pkl"
    result.to_pickle(stable_cache)
    # Also persist the dataset-scoped key used by independent backtests.
    calculator._save_to_cache(expression, result)
    factor.setdefault("cache_location", {})["recomputed_cache_path"] = str(stable_cache)
    return result


def _signal_from_factor(
    factor: dict[str, Any],
    project_root: Path,
    environment: dict[str, str],
) -> pd.Series:
    expression = str(factor.get("factor_expression", "")).strip()
    candidates: list[Path] = []
    if expression:
        candidates.append(
            project_root / "data" / "results" / "factor_cache"
            / f"{hashlib.md5(expression.encode()).hexdigest()}.pkl"
        )
    result_h5 = (factor.get("cache_location") or {}).get("result_h5_path")
    if result_h5:
        candidates.append(Path(result_h5))
    source = next((path for path in candidates if path.exists()), None)
    if source is not None:
        try:
            value = pd.read_pickle(source) if source.suffix == ".pkl" else pd.read_hdf(source)
            signal = _normalize_signal(value)
            available = signal.dropna()
            required_end = pd.Timestamp(
                environment.get("TEST_END_DATE")
                or environment.get("VALID_END_DATE")
                or available.index.get_level_values("datetime").max()
            )
            if not available.empty:
                cache_end = available.index.get_level_values("datetime").max()
                if pd.Timestamp(cache_end) >= required_end - pd.Timedelta(days=7):
                    return signal
        except Exception:
            pass
    return _calculate_signal_from_expression(factor, project_root, environment)


def ensure_factor_signal_cache(
    factor: dict[str, Any],
    project_root: str | Path,
    environment: dict[str, str] | None = None,
) -> str:
    """Ensure a factor has a current reusable signal cache, recomputing if needed."""
    env = dict(os.environ)
    env.update(environment or {})
    project_root = Path(project_root).resolve()
    provider = env.get("QLIB_DATA_DIR") or env.get("WRDS_QLIB_DATA_DIR")
    if not provider:
        raise ValueError("QLIB_DATA_DIR/WRDS_QLIB_DATA_DIR 尚未配置")
    import qlib
    from quantaalpha.market.profile import get_market_profile, qlib_region
    profile = get_market_profile(env)
    qlib.init(provider_uri=provider, region=qlib_region(profile))
    _signal_from_factor(factor, project_root, env)
    expression = str(factor.get("factor_expression", "")).strip()
    return str(
        project_root / "data" / "results" / "factor_cache"
        / f"{hashlib.md5(expression.encode()).hexdigest()}.pkl"
    )


def _compact_curves(analytics: dict[str, Any], max_points: int = 600) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for frequency, payload in analytics.items():
        curves: dict[str, Any] = {}
        for group_name, summary in (payload.get("decile_analytics") or {}).items():
            curve = list(summary.get("curve") or [])
            if not curve:
                continue
            step = max(1, int(np.ceil(len(curve) / max_points)))
            sampled = curve[::step]
            if sampled[-1] != curve[-1]:
                sampled.append(curve[-1])
            curves[group_name] = sampled
        if curves:
            output[frequency] = curves
    return output


def _benchmark_curve(data_api: Any, start: str, end: str,
                     max_points: int = 600) -> list[dict[str, Any]]:
    """Return a compact, locally sourced S&P 500 cumulative-return curve."""
    try:
        raw = data_api.features(
            ["^GSPC"], ["$close"], start_time=start, end_time=end, freq="day"
        )
    except Exception:
        return []
    if raw is None or raw.empty:
        return []
    close = pd.to_numeric(raw.iloc[:, 0], errors="coerce").dropna()
    if close.empty or not np.isfinite(float(close.iloc[0])) or float(close.iloc[0]) == 0:
        return []
    dates = pd.to_datetime(close.index.get_level_values("datetime")
                           if isinstance(close.index, pd.MultiIndex)
                           and "datetime" in close.index.names
                           else close.index.get_level_values(-1))
    cumulative = close.astype(float) / float(close.iloc[0]) - 1.0
    points = [
        {"date": date.strftime("%Y-%m-%d"), "value": round(float(value), 10)}
        for date, value in zip(dates, cumulative)
        if np.isfinite(value)
    ]
    if not points:
        return []
    step = max(1, int(np.ceil(len(points) / max_points)))
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def _save_library_payload(library_path: Path, payload: dict[str, Any]) -> None:
    temp = library_path.with_suffix(library_path.suffix + f".tmp.{os.getpid()}")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temp.replace(library_path)


def _json_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, (float, np.floating)):
            output[str(key)] = round(float(value), 8) if np.isfinite(value) else None
        elif isinstance(value, (int, np.integer)):
            output[str(key)] = int(value)
        else:
            output[str(key)] = value
    return output


def evaluate_factor_split(
    library_path: str | Path,
    factor_id: str,
    split: str,
    project_root: str | Path,
    *,
    force: bool = False,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Calculate and persist one factor's statistics for one configured split."""
    split = str(split).strip().lower()
    if split not in SPLIT_ENV:
        raise ValueError(f"Unsupported split: {split}")
    library_path = Path(library_path).resolve()
    project_root = Path(project_root).resolve()
    from quantaalpha.factors.library import _decode_library_text
    payload = _decode_library_text(library_path.read_text(encoding="utf-8"))
    factors = payload.get("factors") or {}
    if factor_id not in factors:
        raise KeyError(f"Factor not found: {factor_id}")
    factor = factors[factor_id]
    stored = factor.setdefault("split_results", {})
    env = dict(os.environ)
    env.update(environment or {})
    start_key, end_key = SPLIT_ENV[split]
    start = env.get(start_key)
    end = env.get(end_key)
    if not start or not end:
        raise ValueError(f"{split} 区间尚未在系统配置中设置")
    import qlib
    from qlib.data import D
    from quantaalpha.market.profile import (
        apply_market_eligibility, eligibility_fields, get_market_profile, qlib_region,
    )

    provider = env.get("QLIB_DATA_DIR") or env.get("WRDS_QLIB_DATA_DIR")
    if not provider:
        raise ValueError("QLIB_DATA_DIR/WRDS_QLIB_DATA_DIR 尚未配置")
    profile = get_market_profile(env)
    qlib.init(provider_uri=provider, region=qlib_region(profile))

    cached = stored.get(split)
    library_metadata = payload.setdefault("metadata", {})
    benchmark_records = library_metadata.setdefault("benchmark_curves", {})
    benchmark_record = benchmark_records.get(split)
    benchmark_changed = False
    if profile.mode == "us":
        if not (
            isinstance(benchmark_record, dict)
            and str(benchmark_record.get("startDate")) == str(start)
            and str(benchmark_record.get("endDate")) == str(end)
            and isinstance(benchmark_record.get("curve"), list)
            and benchmark_record.get("curve")
        ):
            legacy_curve = cached.get("benchmarkCurve") if isinstance(cached, dict) else None
            benchmark_record = {
                "startDate": start,
                "endDate": end,
                "label": "S&P 500",
                "curve": legacy_curve or _benchmark_curve(D, start, end),
            }
            benchmark_records[split] = benchmark_record
            benchmark_changed = True

    if (
        not force
        and isinstance(cached, dict)
        and str(cached.get("startDate")) == str(start)
        and str(cached.get("endDate")) == str(end)
    ):
        # Keep one benchmark per library/split instead of duplicating the same
        # curve in every factor record.
        if "benchmarkCurve" in cached or "benchmarkLabel" in cached:
            cached.pop("benchmarkCurve", None)
            cached.pop("benchmarkLabel", None)
            benchmark_changed = True
        if benchmark_changed:
            _save_library_payload(library_path, payload)
        return {
            **cached,
            "benchmarkCurve": (benchmark_record or {}).get("curve", []),
            "benchmarkLabel": (benchmark_record or {}).get("label"),
        }

    instruments = D.instruments(profile.instrument)
    market_fields = profile.qlib_classification_fields + eligibility_fields(profile)
    fields = ["Ref($close, -2) / Ref($close, -1) - 1", *market_fields]
    frame = D.features(instruments, fields, start_time=start, end_time=end, freq="day")
    if frame.empty:
        raise ValueError(f"{split} 区间没有可用的 {profile.name} 数据")
    frame.columns = ["label", *[field[1:] for field in market_fields]]
    signal = _signal_from_factor(factor, project_root, env)
    dates = signal.index.get_level_values("datetime")
    signal = signal[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    signal = apply_market_eligibility(signal, frame, env)
    if signal.dropna().empty:
        raise ValueError(f"该因子在 {split} 区间没有可用信号")

    raw_frequencies = env.get("MINING_EVALUATION_FREQUENCIES", "day,week,month")
    frequencies = [
        item.strip().lower() for item in raw_frequencies.split(",")
        if item.strip().lower() in {"day", "week", "month"}
    ] or ["day", "week", "month"]
    _, analytics, group_analytics, metrics = calculate_industry_aware_analytics(
        signal,
        frame["label"],
        frame[list(profile.classification_fields)],
        frequencies=frequencies,
        classification_levels=profile.classification_fields,
        primary_level=profile.primary_classification,
        robustness_level=profile.robustness_classification,
        quantile=float(env.get("LONG_SHORT_QUANTILE", "0.1")),
        min_positions=int(env.get("LONG_SHORT_MIN_POSITIONS", "20")),
        transaction_cost=float(env.get("LONG_SHORT_TRANSACTION_COST", "0.0005")),
        short_borrow_rate=float(env.get("LONG_SHORT_BORROW_RATE", "0")),
    )
    if profile.mode == "crypto" and "funding_rate" in frame:
        from quantaalpha.data.binance_futures_adapter import funding_sensitivity
        metrics.update(funding_sensitivity(signal, frame["funding_rate"]))
    if group_analytics:
        from quantaalpha.backtest.long_short_analytics import flatten_analytics
        robustness = flatten_analytics(group_analytics)
        metrics.update({f"industry.ggroup.robustness.{key}": value for key, value in robustness.items()})

    wrds_root = env.get("WRDS_ROOT", "").strip()
    for frequency, frequency_payload in analytics.items():
        pricing_leg = "long" if profile.mode == "cn" else "long_short"
        daily_returns = (
            frequency_payload.get("portfolio_analytics", {})
            .get(pricing_leg, {})
            .get("daily_net_returns", [])
        )
        if not daily_returns:
            continue
        if profile.mode == "cn":
            from quantaalpha.backtest.china_evaluation import (
                calculate_barra_style_exposures, regress_china_asset_pricing,
            )
            regressions = regress_china_asset_pricing(daily_returns, instruments, start, end)
            metrics.update(calculate_barra_style_exposures(signal, instruments, start, end))
        elif profile.mode == "us" and wrds_root and Path(wrds_root).exists():
            regressions = regress_asset_pricing(daily_returns, wrds_root)
        else:
            regressions = {}
        metrics.update(flatten_asset_pricing(regressions, prefix=f"{frequency}.asset_pricing"))

    result = {
        "split": split,
        "startDate": start,
        "endDate": end,
        "metrics": _json_metrics(metrics),
        "decileCurves": _compact_curves(analytics),
        "computedAt": pd.Timestamp.now(tz="UTC").isoformat(),
        "selectionUse": split == "valid",
        "heldOut": split == "test",
    }
    stored[split] = result
    factor.setdefault("statistics_metadata", {})["display_default_split"] = "test"
    _save_library_payload(library_path, payload)
    return {
        **result,
        "benchmarkCurve": (benchmark_record or {}).get("curve", []),
        "benchmarkLabel": (benchmark_record or {}).get("label"),
    }

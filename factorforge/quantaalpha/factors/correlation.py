"""Correlation analytics for cached factor signals."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _signal_source(info: dict[str, Any], cache_dir: Path) -> Path | None:
    expression = str(info.get("factor_expression") or "")
    if expression:
        cached = cache_dir / f"{hashlib.md5(expression.encode()).hexdigest()}.pkl"
        if cached.is_file():
            return cached
    h5_path = str((info.get("cache_location") or {}).get("result_h5_path") or "")
    if h5_path:
        candidate = Path(h5_path)
        if candidate.is_file():
            return candidate
    return None


def _as_series(raw: Any, factor_name: str) -> pd.Series:
    if isinstance(raw, pd.Series):
        return raw
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise ValueError("factor cache is not a non-empty Series/DataFrame")
    candidates = [factor_name, factor_name.replace(".", "_").replace(" ", "_")]
    for candidate in candidates:
        if candidate in raw.columns:
            return raw[candidate]
    numeric = raw.select_dtypes(include=[np.number])
    if numeric.shape[1] == 1:
        return numeric.iloc[:, 0]
    if raw.shape[1] == 1:
        return raw.iloc[:, 0]
    raise ValueError("cannot identify factor value column")


def _monthly_signal(
    info: dict[str, Any],
    cache_dir: Path,
    start_date: str,
    end_date: str,
) -> pd.Series:
    source = _signal_source(info, cache_dir)
    if source is None:
        raise FileNotFoundError("no factor value cache")
    raw = pd.read_pickle(source) if source.suffix.lower() == ".pkl" else pd.read_hdf(source)
    signal = _as_series(raw, str(info.get("factor_name") or "factor"))
    if not isinstance(signal.index, pd.MultiIndex) or signal.index.nlevels < 2:
        raise ValueError("factor cache must use a datetime/instrument MultiIndex")

    names = list(signal.index.names)
    date_level = names.index("datetime") if "datetime" in names else 0
    instrument_level = names.index("instrument") if "instrument" in names else 1
    dates = pd.to_datetime(signal.index.get_level_values(date_level), errors="coerce")
    instruments = signal.index.get_level_values(instrument_level).astype(str)
    values = pd.to_numeric(signal.to_numpy(), errors="coerce")
    frame = pd.DataFrame({"date": dates, "instrument": instruments, "value": values})
    frame = frame[
        (frame["date"] >= pd.Timestamp(start_date))
        & (frame["date"] <= pd.Timestamp(end_date))
    ].replace([np.inf, -np.inf], np.nan).dropna(subset=["date", "instrument", "value"])
    if frame.empty:
        raise ValueError("no cached observations overlap the requested interval")
    frame["month"] = frame["date"].dt.to_period("M").astype(str)
    # Use the latest available observation for each stock in each month.
    frame = frame.sort_values("date").groupby(["month", "instrument"], sort=False).tail(1)
    output = frame.set_index(["month", "instrument"])["value"].sort_index()
    output.name = str(info.get("factor_id") or info.get("factor_name") or "factor")
    return output


def compute_factor_correlation(
    records: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    method: str = "spearman",
    cache_dir: str | Path = "data/results/factor_cache",
    min_cross_section: int = 20,
) -> dict[str, Any]:
    if method not in {"spearman", "pearson"}:
        raise ValueError("method must be spearman or pearson")
    cache_dir = Path(cache_dir)
    signals: list[pd.Series] = []
    available: list[dict[str, str]] = []
    unavailable: list[dict[str, str]] = []
    for info in records:
        factor_id = str(info.get("factor_id") or "")
        factor_name = str(info.get("factor_name") or factor_id)
        try:
            signal = _monthly_signal(info, cache_dir, start_date, end_date)
            signals.append(signal.rename(factor_id))
            available.append({"factorId": factor_id, "factorName": factor_name})
        except Exception as exc:
            unavailable.append({
                "factorId": factor_id,
                "factorName": factor_name,
                "reason": str(exc),
            })
    if len(signals) < 2:
        raise ValueError("At least two factors with usable value caches are required")

    panel = pd.concat(signals, axis=1, join="outer")
    ids = [item["factorId"] for item in available]
    total = np.zeros((len(ids), len(ids)), dtype=float)
    count = np.zeros((len(ids), len(ids)), dtype=np.int32)
    evaluated_months = 0
    for _, cross_section in panel.groupby(level="month", sort=True):
        cross_section = cross_section.droplevel("month")
        corr = cross_section.corr(method=method, min_periods=min_cross_section).reindex(index=ids, columns=ids)
        values = corr.to_numpy(dtype=float)
        valid = np.isfinite(values)
        total[valid] += values[valid]
        count[valid] += 1
        evaluated_months += 1
    matrix = np.divide(total, count, out=np.full_like(total, np.nan), where=count > 0)
    np.fill_diagonal(matrix, 1.0)

    def serializable(value: float) -> float | None:
        return round(float(value), 6) if np.isfinite(value) else None

    return {
        "method": method,
        "frequency": "monthly_snapshot",
        "aggregation": "mean_of_monthly_cross_sectional_correlations",
        "startDate": start_date,
        "endDate": end_date,
        "minCrossSection": min_cross_section,
        "evaluatedMonths": evaluated_months,
        "factors": available,
        "matrix": [[serializable(value) for value in row] for row in matrix],
        "pairMonths": count.tolist(),
        "unavailable": unavailable,
    }

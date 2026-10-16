"""Validation-only factor redundancy control."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


def _normalize_index(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame.index, pd.MultiIndex) or frame.index.nlevels != 2:
        raise ValueError("Factor correlation pruning requires a two-level index")
    names = [str(name).lower() if name is not None else "" for name in frame.index.names]
    if "datetime" in names:
        date_pos = names.index("datetime")
    elif "date" in names:
        date_pos = names.index("date")
    elif "eom" in names:
        date_pos = names.index("eom")
    else:
        date_pos = 0
        for pos in range(2):
            values = pd.to_datetime(frame.index.get_level_values(pos), errors="coerce")
            if not values.isna().any():
                date_pos = pos
                break
    instrument_pos = 1 - date_pos
    result = frame.copy()
    result.index = pd.MultiIndex.from_arrays(
        [
            pd.to_datetime(frame.index.get_level_values(date_pos)),
            frame.index.get_level_values(instrument_pos).astype(str),
        ],
        names=["datetime", "instrument"],
    )
    return result.sort_index()


def monthly_cross_sectional_spearman(
    factors: pd.DataFrame,
    *,
    start: str,
    end: str,
    min_observations: int = 20,
) -> tuple[pd.DataFrame, int]:
    """Median of month-end cross-sectional Spearman correlation matrices."""
    frame = _normalize_index(factors).replace([np.inf, -np.inf], np.nan)
    dates = frame.index.get_level_values("datetime")
    frame = frame[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    if frame.empty:
        raise ValueError(f"No factor data in validation interval {start} to {end}")

    matrices = []
    date_values = frame.index.get_level_values("datetime")
    for _, positions in pd.Series(range(len(frame)), index=date_values).groupby(date_values.to_period("M")):
        last_date = positions.index.max()
        cross_section = frame.xs(last_date, level="datetime")
        if len(cross_section) < min_observations:
            continue
        matrices.append(cross_section.corr(method="spearman", min_periods=min_observations).to_numpy())
    if not matrices:
        raise ValueError("No usable validation month for factor correlation pruning")
    with np.errstate(all="ignore"):
        median = np.nanmedian(np.stack(matrices), axis=0)
    result = pd.DataFrame(median, index=frame.columns, columns=frame.columns)
    np.fill_diagonal(result.values, 1.0)
    return result, len(matrices)


def validation_rank_ic_scores(
    factors: pd.DataFrame,
    target: pd.Series,
    *,
    start: str,
    end: str,
) -> Dict[str, float]:
    """Absolute mean monthly validation RankIC, used only to choose representatives."""
    frame = _normalize_index(factors)
    target_frame = target.rename("__target__").to_frame()
    target_frame = _normalize_index(target_frame)
    joined = frame.join(target_frame, how="inner")
    dates = joined.index.get_level_values("datetime")
    joined = joined[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    values: Dict[str, list[float]] = {column: [] for column in frame.columns}
    for _, group in joined.groupby(level="datetime", sort=True):
        y = group["__target__"]
        for column in frame.columns:
            corr = group[column].corr(y, method="spearman")
            if pd.notna(corr):
                values[column].append(float(corr))
    return {
        column: abs(float(np.mean(series))) if series else 0.0
        for column, series in values.items()
    }


def prune_correlated_factors(
    factors: pd.DataFrame,
    *,
    start: str,
    end: str,
    threshold: float = 0.85,
    scores: Optional[Dict[str, float]] = None,
) -> tuple[pd.DataFrame, dict]:
    if not 0.5 <= threshold < 1.0:
        raise ValueError("Correlation pruning threshold must be in [0.5, 1.0)")
    correlation, months = monthly_cross_sectional_spearman(factors, start=start, end=end)
    quality = scores or {}
    ordered = sorted(
        correlation.columns,
        key=lambda name: (-float(quality.get(name, 0.0)), str(name)),
    )
    kept: list[str] = []
    clusters: list[dict] = []
    for candidate in ordered:
        match = None
        match_corr = 0.0
        for representative in kept:
            value = correlation.at[candidate, representative]
            if pd.notna(value) and abs(float(value)) >= threshold:
                match = representative
                match_corr = float(value)
                break
        if match is None:
            kept.append(candidate)
            clusters.append({"representative": candidate, "removed": []})
        else:
            cluster = next(item for item in clusters if item["representative"] == match)
            cluster["removed"].append({"factor": candidate, "correlation": round(match_corr, 4)})
    removed = [item for cluster in clusters for item in cluster["removed"]]
    report = {
        "enabled": True,
        "method": "validation_month_end_cross_sectional_spearman",
        "threshold": threshold,
        "validation_period": [start, end],
        "months": months,
        "before_count": len(correlation.columns),
        "after_count": len(kept),
        "removed_count": len(removed),
        "clusters": [cluster for cluster in clusters if cluster["removed"]],
    }
    return factors.loc[:, kept], report

"""Multi-dimensional scoring for evolutionary factor selection."""
from __future__ import annotations

from math import isfinite
import os
from typing import Any, Iterable

import pandas as pd

from quantaalpha.backtest.factor_loader import assess_factor_quality


def _numeric_items(result: Any) -> dict[str, float]:
    if result is None:
        return {}
    if isinstance(result, pd.DataFrame):
        if not len(result.columns):
            return {}
        items: Iterable = result.iloc[:, 0].items()
    elif isinstance(result, pd.Series):
        items = result.items()
    elif isinstance(result, dict):
        items = result.items()
    else:
        return {}
    output = {}
    for key, raw in items:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        value = float(raw)
        if isfinite(value):
            output[str(key)] = value
    return output


def _factor_metric_sets(metrics: dict[str, float]) -> dict[str, dict[str, float]]:
    scoped: dict[str, dict[str, float]] = {}
    for key, value in metrics.items():
        if not key.startswith("factor."):
            continue
        remainder = key[len("factor."):]
        if "." not in remainder:
            continue
        factor_name, metric_name = remainder.split(".", 1)
        scoped.setdefault(factor_name, {})[metric_name] = value
    return scoped or {"combined": metrics}


def _lookup(metrics: dict[str, float], names: tuple[str, ...], suffixes=()):
    for name in names:
        if name in metrics:
            return metrics[name]
    lowered = tuple(str(value).lower() for value in suffixes)
    if lowered:
        for key, value in metrics.items():
            if str(key).lower().endswith(lowered):
                return value
    return None


def extract_evolution_metrics(result: Any) -> dict[str, float | None]:
    """Score every candidate and represent a trajectory by its best factor."""
    raw = _numeric_items(result)
    market_mode = os.environ.get("MARKET_MODE", "us").strip().lower()
    portfolio_leg = "long" if market_mode == "cn" else "long_short"
    candidates = []
    for factor_name, metrics in _factor_metric_sets(raw).items():
        assessment = assess_factor_quality({
            "backtest_results": metrics,
            "market_mode": market_mode,
        })
        candidates.append((float(assessment.get("score", 0.0)), factor_name, metrics, assessment))
    if not candidates:
        return {
            "IC": None, "ICIR": None, "RankIC": None, "RankICIR": None,
            "annualized_return": None, "information_ratio": None,
            "max_drawdown": None, "evolution_score": None,
            "evolution_score_coverage": 0.0, "evolution_factor_count": 0.0,
        }
    score, _, metrics, assessment = max(candidates, key=lambda item: item[0])
    return {
        "IC": _lookup(metrics, ("IC", "ic"), (".IC", ".ic")),
        "ICIR": _lookup(metrics, ("ICIR", "icir"), (".ICIR", ".icir")),
        "RankIC": _lookup(metrics, ("Rank IC", "RankIC", "rank_ic"), (".Rank IC", ".rank_ic")),
        "RankICIR": _lookup(metrics, ("Rank ICIR", "RankICIR", "rank_icir"), (".Rank ICIR", ".rank_icir")),
        "annualized_return": _lookup(
            metrics,
            (f"day.{portfolio_leg}.annualized_net_return", "1day.excess_return_with_cost.annualized_return"),
            (f".{portfolio_leg}.annualized_net_return",),
        ),
        "information_ratio": _lookup(
            metrics,
            (f"day.{portfolio_leg}.sharpe_ratio", "1day.excess_return_with_cost.information_ratio"),
            (f".{portfolio_leg}.sharpe_ratio",),
        ),
        "max_drawdown": _lookup(
            metrics,
            (f"day.{portfolio_leg}.max_drawdown", "1day.excess_return_with_cost.max_drawdown"),
            (f".{portfolio_leg}.max_drawdown",),
        ),
        "evolution_score": score,
        "evolution_score_coverage": float(assessment.get("coverage", 0.0)),
        "evolution_factor_count": float(len(candidates)),
    }

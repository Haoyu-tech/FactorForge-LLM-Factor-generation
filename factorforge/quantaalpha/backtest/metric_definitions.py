"""Single source of truth for the metric definitions shown in the UI.

Each entry names the function that actually computes the metric, so the
frontend can display the formula next to the number together with the exact
source file and line.  Nothing here is a value; it is documentation that is
resolved against the live code at request time.
"""
from __future__ import annotations

import inspect
from typing import Any, Dict

from quantaalpha.backtest import long_short_analytics as lsa

LABEL_EXPRESSION = "Ref($close, -2)/Ref($close, -1) - 1"

METRIC_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "IC": {
        "label": "IC",
        "formula": "mean_t( corr_pearson( score_{i,t}, r_{i,t+1->t+2} ) )",
        "description": (
            "For every test day t, the cross-sectional Pearson correlation between the "
            f"signal and the return from the close of t+1 to the close of t+2, {LABEL_EXPRESSION}, across stocks i; "
            "then the mean over days."
        ),
        "function": lsa.calculate_ic_metrics,
    },
    "Rank IC": {
        "label": "Rank IC",
        "formula": "mean_t( corr_spearman( score_{i,t}, r_{i,t+1->t+2} ) )",
        "description": "Same as IC with Spearman rank correlation instead of Pearson.",
        "function": lsa.calculate_ic_metrics,
    },
    "ICIR": {
        "label": "ICIR",
        "formula": "mean_t(IC_t) / std_t(IC_t)   (sample std, ddof = 1)",
        "description": "Information ratio of the daily IC series.",
        "function": lsa.calculate_ic_metrics,
    },
    "AR": {
        "label": "AR",
        "formula": "equity_T ^ (252 / T) - 1,   equity_t = prod_{s<=t}(1 + net_s)",
        "description": (
            "Annualised net return of the long-short portfolio: each rebalance goes long the top "
            "decile of the signal and short the bottom decile, equal-weighted, 50% / 50% exposure. "
            "Names are chosen from the signal alone; weights drift with returns between rebalances "
            "and transaction costs are charged on turnover from the drifted weights."
        ),
        "function": lsa.calculate_multi_frequency_analytics,
    },
    "MDD": {
        "label": "MDD",
        "formula": "min_t( equity_t / max_{s<=t}(equity_s) - 1 )",
        "description": "Maximum drawdown of the same long-short net equity curve (negative number).",
        "function": lsa.calculate_multi_frequency_analytics,
    },
}


def _source_location(function) -> Dict[str, Any]:
    try:
        file = inspect.getsourcefile(function) or ""
        _, line = inspect.getsourcelines(function)
    except (OSError, TypeError):
        return {"file": "", "line": None}
    return {"file": file, "line": line}


def metric_definitions_payload() -> Dict[str, Dict[str, Any]]:
    """JSON-ready definitions with the live source location of every formula."""
    payload: Dict[str, Dict[str, Any]] = {}
    for key, entry in METRIC_DEFINITIONS.items():
        fn = entry["function"]
        payload[key] = {
            "label": entry["label"],
            "formula": entry["formula"],
            "description": entry["description"],
            "implementation": f"{fn.__module__}.{fn.__name__}",
            **_source_location(fn),
        }
    return payload

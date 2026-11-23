"""Read the per-round LLM feedback of a mining run from its trajectory pool.

The evolution controller rewrites ``<log_root>/trajectory_pool.json`` after every
round, so this works both while a run is in progress and after it finishes.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

POOL_FILENAME = "trajectory_pool.json"
_EXPERIMENT_ID = re.compile(r"exp_\d{8}_\d{6}")


class FeedbackNotReady(Exception):
    """The pool file exists but is mid-write; the caller should retry."""


def is_experiment_id(value: str) -> bool:
    """True only for a run folder name such as exp_20261121_181720 (no path parts)."""
    return bool(_EXPERIMENT_ID.fullmatch(value or ""))


def _decision(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    return str(value).strip().lower() in {"true", "1", "yes"}


def _finite_or_none(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(record: dict) -> dict:
    details = record.get("feedback_details") or {}
    hypothesis = (record.get("hypothesis_details") or {}).get("hypothesis") or record.get("hypothesis") or ""
    return {
        "trajectoryId": record.get("trajectory_id", ""),
        "directionId": record.get("direction_id"),
        "roundIdx": record.get("round_idx"),
        "phase": record.get("phase", ""),
        "parentIds": list(record.get("parent_ids") or []),
        "createdAt": record.get("created_at", ""),
        "hypothesis": str(hypothesis),
        "decision": _decision(details.get("decision")),
        "observations": str(details.get("observations") or ""),
        "hypothesisEvaluation": str(details.get("hypothesis_evaluation") or ""),
        "newHypothesis": str(details.get("new_hypothesis") or ""),
        "reason": str(details.get("reason") or ""),
        "factors": [
            {"name": f.get("name", ""), "expression": f.get("expression", "")}
            for f in record.get("factors") or [] if isinstance(f, dict)
        ],
        "metrics": {k: _finite_or_none(v) for k, v in (record.get("backtest_metrics") or {}).items()},
    }


def load_round_feedback(log_root: str | Path) -> dict:
    path = Path(log_root) / POOL_FILENAME
    if not path.is_file():
        return {"available": False, "savedAt": None, "rounds": []}
    try:
        pool = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise FeedbackNotReady(f"{path.name} is being written: {error}") from error
    trajectories = pool.get("trajectories") or {}
    records = trajectories.values() if isinstance(trajectories, dict) else trajectories
    rounds = sorted((_round(r) for r in records if isinstance(r, dict)), key=lambda r: r["createdAt"])
    return {"available": True, "savedAt": pool.get("saved_at"), "rounds": rounds}

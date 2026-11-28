"""Summaries of past mining runs, read from their log folders.

Each ``log/exp_<YYYYMMDD_HHMMSS>/`` folder is one run. A summary combines:

- ``run.json`` (see ``run_record``): prompt, LLM, token use, outcome, timing;
- ``directions.json``: the exploration directions planning generated;
- ``evolution_state.json``: planned and completed rounds, for runs with no record;
- ``trajectory_pool.json`` (via ``round_feedback``): per-round decisions and
  validation-split metrics;
- the run's factor library in ``data/factorlib``: factor count and scope.

Every number comes from those files. Missing pieces stay None rather than
being guessed.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from quantaalpha.utils.round_feedback import (
    FeedbackNotReady,
    is_experiment_id,
    load_round_feedback,
)
from quantaalpha.utils.run_record import DIRECTIONS_FILE, read_json, read_run_record

LIBRARY_PREFIX = "all_factors_library_"

# (path, mtime_ns, size) -> parsed value. Pools and libraries are megabytes,
# and the list view reads every one of them; re-parse only what changed.
_cache: dict[tuple[str, int, int], Any] = {}


def _cached(path: Path, parse: Callable[[Path], Any]) -> Any:
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _cache:
        for stale in [k for k in _cache if k[0] == key[0]]:
            del _cache[stale]
        _cache[key] = parse(path)
    return _cache[key]


def _pool_rounds(log_root: Path) -> list[dict[str, Any]] | None:
    """Rounds from the trajectory pool; None if there is none or it is mid-write."""
    def parse(_: Path) -> list[dict[str, Any]] | None:
        try:
            report = load_round_feedback(log_root)
        except FeedbackNotReady:
            return None
        return report["rounds"] if report["available"] else None

    return _cached(log_root / "trajectory_pool.json", parse)


def _library_summary(path: Path) -> dict[str, Any] | None:
    def parse(p: Path) -> dict[str, Any] | None:
        try:
            from quantaalpha.factors.library import _decode_library_text
            library = _decode_library_text(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        metadata = library.get("metadata") or {}
        return {
            "file": p.name,
            "factorCount": len(library.get("factors") or {}),
            "marketMode": metadata.get("market_mode"),
            "market": metadata.get("market"),
            "scopeLabel": metadata.get("scope_label"),
            "splitWindows": metadata.get("split_windows"),
        }

    return _cached(path, parse)


def find_library(experiment_id: str, record: dict[str, Any] | None, factorlib_dir: Path) -> Path | None:
    """The run's factor library: the recorded suffix, else the default name."""
    suffix = ((record or {}).get("settings") or {}).get("librarySuffix")
    if suffix:
        candidate = factorlib_dir / f"{LIBRARY_PREFIX}{suffix}.json"
        if candidate.exists():
            return candidate
    # The default suffix is <market>_<universe>_<experiment id>.
    matches = sorted(factorlib_dir.glob(f"{LIBRARY_PREFIX}*_{experiment_id}.json"))
    return matches[0] if matches else None


def _start_from_name(name: str) -> str | None:
    try:
        return datetime.strptime(name, "exp_%Y%m%d_%H%M%S").isoformat()
    except ValueError:
        return None


def _best_round(rounds: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The round the pipeline itself ranks highest, by evolution score."""
    scored = [r for r in rounds if r["metrics"].get("evolution_score") is not None]
    if not scored:
        return None
    best = max(scored, key=lambda r: r["metrics"]["evolution_score"])
    m = best["metrics"]
    return {
        "directionId": best["directionId"],
        "roundIdx": best["roundIdx"],
        "phase": best["phase"],
        "decision": best["decision"],
        "evolutionScore": m.get("evolution_score"),
        "ic": m.get("IC"),
        "rankIc": m.get("RankIC"),
        "annualizedReturn": m.get("annualized_return"),
        "sharpe": m.get("information_ratio"),
        "maxDrawdown": m.get("max_drawdown"),
    }


def summarize_run(log_root: Path, factorlib_dir: Path, *, detail: bool = False) -> dict[str, Any]:
    log_root = Path(log_root)
    experiment_id = log_root.name
    record = read_run_record(log_root) or {}
    directions = read_json(log_root / DIRECTIONS_FILE) or {}
    state = read_json(log_root / "evolution_state.json") or {}
    rounds = _pool_rounds(log_root)
    library_path = find_library(experiment_id, record, factorlib_dir)
    library = _library_summary(library_path) if library_path else None

    progress = record.get("progress") or {}
    usage = record.get("usage")
    summary: dict[str, Any] = {
        "experimentId": experiment_id,
        "recordSource": record.get("source"),
        "status": record.get("status") or "unknown",
        "statusMessage": record.get("statusMessage"),
        "direction": record.get("direction") or directions.get("userDirection"),
        "startedAt": record.get("startedAt") or _start_from_name(experiment_id),
        "completedAt": record.get("completedAt"),
        "completedAtEstimated": bool(record.get("completedAtEstimated", True)) if record else True,
        "durationSeconds": record.get("durationSeconds"),
        "llm": record.get("llm"),
        "usage": usage,
        "roundsPlanned": progress.get("totalRounds") or (state.get("config") or {}).get("max_rounds"),
        "roundsReached": progress.get("currentRound") or state.get("current_round"),
        "rounds": {
            "total": len(rounds),
            "accepted": sum(1 for r in rounds if r["decision"] is True),
            "rejected": sum(1 for r in rounds if r["decision"] is False),
            # Runs before rejected-round feedback was kept leave these unset.
            "noFeedback": sum(1 for r in rounds if r["decision"] is None),
        } if rounds else None,
        "best": _best_round(rounds) if rounds else None,
        "library": library,
        "hasResults": bool(rounds) or bool(library and library["factorCount"]),
    }
    if detail:
        summary["plannedDirections"] = (
            directions.get("plannedDirections") or record.get("plannedDirections") or []
        )
        summary["settings"] = record.get("settings") or {}
        summary["evolutionConfig"] = state.get("config") or {}
        summary["scores"] = [
            {
                "createdAt": r["createdAt"],
                "directionId": r["directionId"],
                "roundIdx": r["roundIdx"],
                "phase": r["phase"],
                "decision": r["decision"],
                "rankIc": r["metrics"].get("RankIC"),
                "evolutionScore": r["metrics"].get("evolution_score"),
            }
            for r in rounds or []
        ]
    return summary


def list_runs(log_dir: Path, factorlib_dir: Path) -> list[dict[str, Any]]:
    """Every run folder, newest first."""
    folders = [p for p in Path(log_dir).glob("exp_*") if p.is_dir() and is_experiment_id(p.name)]
    return [summarize_run(p, factorlib_dir) for p in sorted(folders, key=lambda p: p.name, reverse=True)]


if __name__ == "__main__":  # quick look: python -m quantaalpha.utils.run_history
    for run in list_runs(Path("log"), Path("data/factorlib")):
        print(json.dumps({k: run[k] for k in ("experimentId", "status", "rounds", "best")}, default=str))

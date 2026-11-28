"""A plain-JSON record of one mining run, kept in the run's log folder.

Two files, each with a single writer so they never race:

- ``log/<exp_id>/run.json`` is written by the backend: the direction prompt, the
  LLM channel, token use and cost, final status, start/end time and duration,
  and the launch settings. It is rewritten as the run progresses, so a run that
  dies mid-way still leaves its last known state.
- ``log/<exp_id>/directions.json`` is written by the mining pipeline: the
  user's direction and the exploration directions planning generated from it.
  CLI runs, which bypass the backend, get this file too.

Before these files existed the prompt survived only inside pickled loop
snapshots, which stop loading once the classes they reference change.
``backfill_run_record`` copies what those snapshots hold into ``run.json``.

Run ``python -m quantaalpha.utils.run_record --backfill [log_dir]`` to backfill.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

RUN_RECORD = "run.json"
DIRECTIONS_FILE = "directions.json"
SCHEMA_VERSION = 1
ACTIVE_STATUSES = {"pending", "running"}


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON so a reader sees either the old file or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path) -> dict[str, Any] | None:
    """The JSON object at ``path``, or None if it is missing or unreadable."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_run_record(log_root: Path, record: dict[str, Any]) -> None:
    write_json_atomic(Path(log_root) / RUN_RECORD, {"schemaVersion": SCHEMA_VERSION, **record})


def read_run_record(log_root: Path) -> dict[str, Any] | None:
    return read_json(Path(log_root) / RUN_RECORD)


def write_directions(log_root: Path, user_direction: str | None, planned: list[str | None]) -> None:
    write_json_atomic(Path(log_root) / DIRECTIONS_FILE, {
        "schemaVersion": SCHEMA_VERSION,
        "userDirection": user_direction,
        "plannedDirections": list(planned),
        "createdAt": datetime.now().isoformat(),
    })


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _last_activity(log_root: Path, record: dict[str, Any]) -> datetime | None:
    """The latest moment the run is known to have been alive."""
    candidates = [_parse_time(record.get("updatedAt"))]
    pool = read_json(log_root / "trajectory_pool.json")
    if pool:
        candidates.append(_parse_time(pool.get("saved_at")))
    known = [moment for moment in candidates if moment is not None]
    return max(known) if known else None


def mark_interrupted_runs(log_dir: Path) -> list[str]:
    """Close records the backend left as running when it stopped.

    Only the backend runs mining jobs, so when it starts no run it launched
    earlier can still be reporting to it. The end time is the last moment the
    run was seen alive, flagged as an estimate.
    """
    closed = []
    for record_path in sorted(Path(log_dir).glob(f"exp_*/{RUN_RECORD}")):
        record = read_json(record_path)
        if not record or record.get("status") not in ACTIVE_STATUSES:
            continue
        log_root = record_path.parent
        ended = _last_activity(log_root, record)
        started = _parse_time(record.get("startedAt"))
        record.update({
            "status": "interrupted",
            "statusMessage": (
                "The backend stopped while this run was in progress, so its outcome, "
                "and any token use after that point, were not recorded."
            ),
            "completedAt": ended.isoformat() if ended else None,
            "completedAtEstimated": True,
            "durationSeconds": (
                round((ended - started).total_seconds(), 1) if ended and started else None
            ),
            "updatedAt": datetime.now().isoformat(),
        })
        write_json_atomic(record_path, record)
        closed.append(log_root.name)
    return closed


def _start_from_folder_name(name: str) -> datetime | None:
    try:
        return datetime.strptime(name, "exp_%Y%m%d_%H%M%S")
    except ValueError:
        return None


def _load_snapshot(path: Path) -> Any:
    # These are the pipeline's own session snapshots, written by this project.
    import pickle
    with open(path, "rb") as handle:
        return pickle.load(handle)


def backfill_run_record(log_root: Path) -> dict[str, Any] | None:
    """Write ``run.json`` for a pre-record run from what its folder still holds.

    Recovers the direction prompt and the planned directions from the session
    snapshots and an estimated start and end from the folder name and the
    trajectory pool. The LLM channel, token use and cost, and the final status
    were never written to disk, so they stay null and ``unknown``. Returns the
    record, or None when the run already has one or no snapshot can be read.
    """
    log_root = Path(log_root)
    if (log_root / RUN_RECORD).exists():
        return None

    user_direction = None
    planned: dict[str, str | None] = {}
    for snapshot in sorted(log_root.glob("original_*/__session__/*/0_factor_propose")):
        try:
            loop = _load_snapshot(snapshot)
        # A stale snapshot can fail in many ways (missing module or attribute,
        # truncated file); any of them just means this one cannot be read.
        except Exception as error:  # noqa: BLE001
            print(f"{snapshot}: unreadable ({type(error).__name__}: {error})", file=sys.stderr)
            continue
        user_direction = user_direction or getattr(loop, "user_initial_direction", None)
        branch = snapshot.parts[-4]  # original_<round>_<direction>
        planned.setdefault(branch, getattr(loop, "potential_direction", None))
    if user_direction is None and not any(planned.values()):
        return None

    started = _start_from_folder_name(log_root.name)
    pool = read_json(log_root / "trajectory_pool.json") or {}
    ended = _parse_time(pool.get("saved_at"))
    state = read_json(log_root / "evolution_state.json") or {}
    record = {
        "source": "backfilled",
        "experimentId": log_root.name,
        "taskId": None,
        "status": "unknown",
        "statusMessage": "Recorded before run records existed; the outcome was not saved.",
        "direction": user_direction,
        "plannedDirections": [planned[key] for key in sorted(planned)],
        "llm": None,
        "usage": None,
        "startedAt": started.isoformat() if started else None,
        "completedAt": ended.isoformat() if ended else None,
        "completedAtEstimated": True,
        "durationSeconds": (
            round((ended - started).total_seconds(), 1) if ended and started else None
        ),
        "progress": {
            "currentRound": state.get("current_round"),
            "totalRounds": (state.get("config") or {}).get("max_rounds"),
        },
        "settings": state.get("config") or {},
        "updatedAt": datetime.now().isoformat(),
    }
    write_run_record(log_root, record)
    return record


def _main(argv: list[str]) -> int:
    if not argv or argv[0] != "--backfill":
        print(__doc__)
        return 2
    log_dir = Path(argv[1]) if len(argv) > 1 else Path("log")
    for log_root in sorted(log_dir.glob("exp_*")):
        record = backfill_run_record(log_root)
        if record is None:
            reason = "has run.json" if (log_root / RUN_RECORD).exists() else "no readable snapshot"
            print(f"{log_root.name}: skipped ({reason})")
        else:
            prompt = (record["direction"] or "").replace("\n", " ")
            print(f"{log_root.name}: backfilled; prompt: {prompt[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))

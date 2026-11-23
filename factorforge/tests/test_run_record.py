import json
import pickle
from types import SimpleNamespace

from quantaalpha.utils.run_record import (
    backfill_run_record,
    mark_interrupted_runs,
    read_run_record,
    write_directions,
    write_run_record,
)


def _record(status, **extra):
    return {
        "experimentId": "exp_20261201_090000",
        "status": status,
        "direction": "Late reporters underperform",
        "startedAt": "2026-12-01T09:00:00",
        "updatedAt": "2026-12-01T09:30:00",
        **extra,
    }


def test_record_round_trips_and_leaves_no_temp_file(tmp_path):
    run = tmp_path / "exp_20261201_090000"
    write_run_record(run, _record("completed", durationSeconds=1800.0))

    record = read_run_record(run)
    assert record["schemaVersion"] == 1
    assert record["direction"] == "Late reporters underperform"
    assert [p.name for p in run.iterdir()] == ["run.json"]


def test_unreadable_record_reads_as_none(tmp_path):
    (tmp_path / "run.json").write_text("{half", encoding="utf-8")
    assert read_run_record(tmp_path) is None
    assert read_run_record(tmp_path / "missing") is None


def test_directions_file_keeps_user_prompt_and_planned_directions(tmp_path):
    write_directions(tmp_path, "momentum", ["direction A", None])
    saved = json.loads((tmp_path / "directions.json").read_text(encoding="utf-8"))
    assert saved["userDirection"] == "momentum"
    assert saved["plannedDirections"] == ["direction A", None]


def test_running_record_is_closed_as_interrupted_at_last_activity(tmp_path):
    run = tmp_path / "exp_20261201_090000"
    write_run_record(run, _record("running"))
    # The pool was saved after the record's last update, so it is the later sign of life.
    (run / "trajectory_pool.json").write_text(
        json.dumps({"saved_at": "2026-12-01T09:45:00"}), encoding="utf-8")

    assert mark_interrupted_runs(tmp_path) == ["exp_20261201_090000"]
    record = read_run_record(run)
    assert record["status"] == "interrupted"
    assert record["completedAt"] == "2026-12-01T09:45:00"
    assert record["completedAtEstimated"] is True
    assert record["durationSeconds"] == 2700.0


def test_finished_records_are_left_alone(tmp_path):
    for day, status in enumerate(("completed", "cancelled", "failed"), start=1):
        write_run_record(tmp_path / f"exp_2026120{day}_090000", _record(status))
    before = {p: p.read_text() for p in tmp_path.glob("*/run.json")}

    assert mark_interrupted_runs(tmp_path) == []
    assert {p: p.read_text() for p in tmp_path.glob("*/run.json")} == before


def _snapshot(run, branch, **attrs):
    path = run / branch / "__session__" / "0" / "0_factor_propose"
    path.parent.mkdir(parents=True)
    path.write_bytes(pickle.dumps(SimpleNamespace(**attrs)))


def test_backfill_recovers_prompt_directions_and_timing(tmp_path):
    run = tmp_path / "exp_20261121_181720"
    _snapshot(run, "original_00_00", user_initial_direction="Late reporters", potential_direction="peer lag")
    _snapshot(run, "original_00_01", user_initial_direction="Late reporters", potential_direction="own lag")
    (run / "trajectory_pool.json").write_text(
        json.dumps({"saved_at": "2026-11-21T20:30:54"}), encoding="utf-8")
    (run / "evolution_state.json").write_text(
        json.dumps({"current_round": 20, "config": {"max_rounds": 20, "num_directions": 2}}), encoding="utf-8")

    assert backfill_run_record(run) is not None
    saved = read_run_record(run)
    assert saved["source"] == "backfilled"
    assert saved["direction"] == "Late reporters"
    assert saved["plannedDirections"] == ["peer lag", "own lag"]
    assert saved["status"] == "unknown"
    assert saved["llm"] is None and saved["usage"] is None
    assert saved["startedAt"] == "2026-11-21T18:17:20"
    assert saved["durationSeconds"] == 8014.0
    assert saved["progress"] == {"currentRound": 20, "totalRounds": 20}


def test_backfill_never_overwrites_and_skips_runs_without_snapshots(tmp_path):
    kept = tmp_path / "exp_20261201_090000"
    write_run_record(kept, _record("completed"))
    _snapshot(kept, "original_00_00", user_initial_direction="other")
    assert backfill_run_record(kept) is None
    assert read_run_record(kept)["direction"] == "Late reporters underperform"

    empty = tmp_path / "exp_20261202_090000"
    empty.mkdir()
    assert backfill_run_record(empty) is None
    assert not (empty / "run.json").exists()

"""Per-round LLM feedback is read from a run's trajectory pool for the dashboard."""
import json

import pytest

from quantaalpha.utils.round_feedback import (
    FeedbackNotReady,
    is_experiment_id,
    load_round_feedback,
)


def _trajectory(tid, created_at, decision, **overrides):
    record = {
        "trajectory_id": tid,
        "direction_id": 1,
        "round_idx": 0,
        "phase": "original",
        "hypothesis": "Hypothesis: late reporters underperform",
        "hypothesis_details": {"hypothesis": "late reporters underperform"},
        "factors": [{"name": "Lag", "expression": "-$report_lag_days", "description": "d", "code": "x" * 500}],
        "backtest_result": None,
        "backtest_metrics": {"IC": 0.01, "RankIC": float("nan"), "max_drawdown": -0.09},
        "feedback": "Observations: ...",
        "feedback_details": {
            "observations": "obs",
            "hypothesis_evaluation": "eval",
            "new_hypothesis": "next",
            "reason": "why",
            "decision": decision,
        },
        "parent_ids": [],
        "created_at": created_at,
        "extra_info": {},
    }
    record.update(overrides)
    return record


def _write_pool(tmp_path, trajectories):
    pool = {
        "trajectories": {t["trajectory_id"]: t for t in trajectories},
        "by_direction": {}, "by_phase": {}, "saved_at": "2026-11-21T20:30:00",
    }
    # json.dump writes NaN as a bare token, exactly as TrajectoryPool._save does.
    (tmp_path / "trajectory_pool.json").write_text(json.dumps(pool))
    return tmp_path


def test_rounds_are_ordered_by_creation_and_flattened(tmp_path):
    log_root = _write_pool(tmp_path, [
        _trajectory("b", "2026-11-21T19:00:00", True, phase="mutation", round_idx=1, parent_ids=["a"]),
        _trajectory("a", "2026-11-21T18:00:00", "False"),
    ])
    report = load_round_feedback(log_root)
    assert report["available"] is True
    assert report["savedAt"] == "2026-11-21T20:30:00"
    assert [r["trajectoryId"] for r in report["rounds"]] == ["a", "b"]
    first, second = report["rounds"]
    assert first["decision"] is False  # string "False" from older pools
    assert second["decision"] is True
    assert second["phase"] == "mutation" and second["parentIds"] == ["a"]
    assert first["hypothesis"] == "late reporters underperform"
    assert first["observations"] == "obs"
    assert first["hypothesisEvaluation"] == "eval"
    assert first["newHypothesis"] == "next"
    assert first["reason"] == "why"
    # Code is bulky and not needed to read feedback.
    assert first["factors"] == [{"name": "Lag", "expression": "-$report_lag_days"}]


def test_non_finite_metrics_become_null_so_the_response_is_valid_json(tmp_path):
    report = load_round_feedback(_write_pool(tmp_path, [_trajectory("a", "2026-11-21T18:00:00", False)]))
    metrics = report["rounds"][0]["metrics"]
    assert metrics["IC"] == 0.01 and metrics["RankIC"] is None
    json.dumps(report, allow_nan=False)


def test_round_without_feedback_has_unknown_decision(tmp_path):
    report = load_round_feedback(_write_pool(tmp_path, [
        _trajectory("a", "2026-11-21T18:00:00", None, feedback_details={}),
    ]))
    row = report["rounds"][0]
    assert row["decision"] is None and row["observations"] == ""


def test_missing_pool_is_reported_as_not_available(tmp_path):
    assert load_round_feedback(tmp_path) == {"available": False, "savedAt": None, "rounds": []}


def test_half_written_pool_raises_not_ready(tmp_path):
    (tmp_path / "trajectory_pool.json").write_text('{"trajectories": {"a": ')
    with pytest.raises(FeedbackNotReady):
        load_round_feedback(tmp_path)


def test_only_run_folder_names_are_accepted_as_experiment_ids():
    assert is_experiment_id("exp_20261121_181720")
    for bad in ("", "exp_2026", "../exp_20261121_181720", "exp_20261121_181720/..", "us_sp500_exp_20261121_181720"):
        assert not is_experiment_id(bad)

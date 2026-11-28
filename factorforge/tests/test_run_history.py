"""Run History summarises each log/exp_* folder from the files it left."""
import json

from quantaalpha.utils.run_history import find_library, list_runs, summarize_run
from quantaalpha.utils.run_record import write_directions, write_run_record


def _round(tid, created_at, decision, score, rank_ic, **extra):
    return {
        "trajectory_id": tid, "direction_id": 0, "round_idx": extra.pop("round_idx", 0),
        "phase": "original", "hypothesis": "h", "factors": [],
        "backtest_metrics": {"RankIC": rank_ic, "information_ratio": 0.5, "evolution_score": score},
        "feedback_details": {"decision": decision} if decision is not None else None,
        "parent_ids": [], "created_at": created_at, **extra,
    }


def _pool(run, rounds):
    run.mkdir(parents=True, exist_ok=True)
    (run / "trajectory_pool.json").write_text(json.dumps({
        "trajectories": {r["trajectory_id"]: r for r in rounds}, "saved_at": "2026-12-01T10:00:00",
    }))


def _library(factorlib, name, factors=3):
    factorlib.mkdir(parents=True, exist_ok=True)
    (factorlib / name).write_text(json.dumps({
        "metadata": {"market_mode": "us", "market": "sp500", "scope_label": "S&P 500",
                     "split_windows": {"train": ["1987-01-01", "2010-12-31"]}},
        "factors": {f"f{i}": {"factor_name": f"F{i}"} for i in range(factors)},
    }))


def test_recorded_run_combines_record_pool_and_library(tmp_path):
    run, factorlib = tmp_path / "log" / "exp_20261201_090000", tmp_path / "factorlib"
    _pool(run, [
        _round("a", "2026-12-01T09:10:00", True, 40.0, 0.010),
        _round("b", "2026-12-01T09:20:00", False, 55.0, 0.004, round_idx=1),
        _round("c", "2026-12-01T09:30:00", None, 30.0, 0.020, round_idx=2),
    ])
    write_run_record(run, {
        "source": "backend", "status": "completed", "direction": "late reporters",
        "startedAt": "2026-12-01T09:00:00", "completedAt": "2026-12-01T10:00:00",
        "completedAtEstimated": False, "durationSeconds": 3600.0,
        "usage": {"totalTokens": 1200, "costUsd": 0.02},
        "progress": {"currentRound": 3, "totalRounds": 3},
        "settings": {"librarySuffix": "us_sp500_custom"},
    })
    _library(factorlib, "all_factors_library_us_sp500_custom.json", factors=5)

    run_summary = summarize_run(run, factorlib)

    assert run_summary["status"] == "completed"
    assert run_summary["direction"] == "late reporters"
    assert run_summary["completedAtEstimated"] is False
    assert run_summary["rounds"] == {"total": 3, "accepted": 1, "rejected": 1, "noFeedback": 1}
    # Best is the pipeline's own ranking (evolution score), not the highest Rank IC.
    assert run_summary["best"]["rankIc"] == 0.004
    assert run_summary["best"]["evolutionScore"] == 55.0
    assert run_summary["library"]["file"] == "all_factors_library_us_sp500_custom.json"
    assert run_summary["library"]["factorCount"] == 5
    assert run_summary["usage"]["costUsd"] == 0.02
    assert run_summary["hasResults"] is True


def test_run_without_record_falls_back_to_folder_files(tmp_path):
    run, factorlib = tmp_path / "log" / "exp_20261202_081500", tmp_path / "factorlib"
    run.mkdir(parents=True)
    write_directions(run, "momentum", ["dir A", "dir B"])
    (run / "evolution_state.json").write_text(json.dumps({"current_round": 2, "config": {"max_rounds": 4}}))
    _library(factorlib, "all_factors_library_us_sp500_exp_20261202_081500.json")

    detail = summarize_run(run, factorlib, detail=True)

    assert detail["status"] == "unknown"
    assert detail["direction"] == "momentum"
    assert detail["startedAt"] == "2026-12-02T08:15:00"
    assert detail["completedAtEstimated"] is True
    assert (detail["roundsReached"], detail["roundsPlanned"]) == (2, 4)
    assert detail["plannedDirections"] == ["dir A", "dir B"]
    assert detail["rounds"] is None and detail["best"] is None
    assert detail["hasResults"] is True  # the library has factors


def test_detail_lists_round_scores_in_completion_order(tmp_path):
    run = tmp_path / "log" / "exp_20261201_090000"
    _pool(run, [
        _round("late", "2026-12-01T09:30:00", True, 50.0, 0.02, round_idx=1),
        _round("early", "2026-12-01T09:10:00", False, 40.0, 0.01),
    ])
    scores = summarize_run(run, tmp_path / "factorlib", detail=True)["scores"]
    assert [(s["roundIdx"], s["decision"], s["rankIc"]) for s in scores] == [(0, False, 0.01), (1, True, 0.02)]


def test_empty_folder_has_no_results(tmp_path):
    run = tmp_path / "log" / "exp_20261203_000000"
    run.mkdir(parents=True)
    run_summary = summarize_run(run, tmp_path / "factorlib")
    assert run_summary["hasResults"] is False
    assert run_summary["direction"] is None and run_summary["library"] is None


def test_list_is_newest_first_and_skips_other_folders(tmp_path):
    log = tmp_path / "log"
    for name in ("exp_20261201_090000", "exp_20261203_090000", "exp_20261202_090000", "notes", "exp_bad"):
        (log / name).mkdir(parents=True)
    (log / "backend.log").write_text("")
    ids = [r["experimentId"] for r in list_runs(log, tmp_path / "factorlib")]
    assert ids == ["exp_20261203_090000", "exp_20261202_090000", "exp_20261201_090000"]


def test_library_lookup_prefers_recorded_suffix_then_default_name(tmp_path):
    factorlib = tmp_path / "factorlib"
    _library(factorlib, "all_factors_library_us_sp500_exp_20261201_090000.json")
    _library(factorlib, "all_factors_library_us_sp500_mine.json")
    recorded = {"settings": {"librarySuffix": "us_sp500_mine"}}
    assert find_library("exp_20261201_090000", recorded, factorlib).name == "all_factors_library_us_sp500_mine.json"
    assert find_library("exp_20261201_090000", None, factorlib).name.endswith("exp_20261201_090000.json")
    assert find_library("exp_20261201_090000", {"settings": {"librarySuffix": "gone"}}, factorlib) is not None
    assert find_library("exp_20991231_000000", None, factorlib) is None

"""Rejected trajectories must keep their feedback for mutation and crossover.

``HypothesisFeedback.__bool__`` returns the "replace best result" decision, so
``if feedback:`` is False for every rejected round. The controller used that
test for presence and stored an empty feedback string, which left the mutation
prompt with "N/A" in place of the reasons the parent failed.
"""
from quantaalpha.core.proposal import HypothesisFeedback
from quantaalpha.pipeline.evolution.controller import EvolutionConfig, EvolutionController
from quantaalpha.pipeline.evolution.trajectory import RoundPhase


def _feedback(decision: bool) -> HypothesisFeedback:
    return HypothesisFeedback(
        observations="Net long-short return is negative after costs.",
        hypothesis_evaluation="The hypothesis is not supported.",
        new_hypothesis="Test a slower signal.",
        reason="Turnover dominates the gross return.",
        decision=decision,
    )


def _trajectory(feedback):
    controller = EvolutionController(EvolutionConfig(num_directions=1))
    task = {
        "phase": RoundPhase.ORIGINAL, "direction_id": 0, "round_idx": 0,
        "parent_trajectories": [],
    }
    return controller.create_trajectory_from_loop_result(
        task=task, hypothesis=None, experiment=None, feedback=feedback,
    )


def test_rejected_feedback_is_kept():
    trajectory = _trajectory(_feedback(decision=False))
    assert "Turnover dominates the gross return." in trajectory.feedback
    assert trajectory.feedback_details["observations"].startswith("Net long-short")
    assert trajectory.feedback_details["decision"] is False


def test_accepted_feedback_is_kept():
    trajectory = _trajectory(_feedback(decision=True))
    assert "Turnover dominates the gross return." in trajectory.feedback
    assert trajectory.feedback_details["decision"] is True


def test_missing_feedback_stays_empty():
    trajectory = _trajectory(None)
    assert trajectory.feedback == ""
    assert trajectory.feedback_details == {}

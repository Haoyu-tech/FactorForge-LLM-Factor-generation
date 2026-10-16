import pandas as pd

from quantaalpha.pipeline.evolution.scoring import extract_evolution_metrics
from quantaalpha.pipeline.evolution.trajectory import RoundPhase, StrategyTrajectory


def _result(metrics):
    return pd.DataFrame({"value": pd.Series(metrics, dtype=float)})


def test_evolution_score_uses_multiple_evidence_groups():
    result = extract_evolution_metrics(_result({
        "factor.good.IC": 0.025,
        "factor.good.Rank IC": 0.022,
        "factor.good.ICIR": 0.45,
        "factor.good.day.long_short.annualized_gross_return": 0.15,
        "factor.good.day.long_short.annualized_net_return": 0.12,
        "factor.good.day.long_short.sharpe_ratio": 1.2,
        "factor.good.day.long_short.max_drawdown": -0.16,
        "factor.good.day.long_short.average_turnover_per_rebalance": 0.35,
        "factor.good.day.decile_monotonicity": 0.80,
        "factor.good.day.asset_pricing.ff5_mom.alpha_t_stat": 2.8,
        "factor.good.day.asset_pricing.ff5_mom.alpha_p_value": 0.01,
        "factor.weak.Rank IC": 0.04,
    }))
    assert result["evolution_score"] > 60
    assert result["RankIC"] == 0.022
    assert result["evolution_score_coverage"] >= 0.55


def test_high_rank_ic_alone_cannot_dominate_balanced_factor():
    rank_only = extract_evolution_metrics(_result({"factor.one.Rank IC": 0.08}))
    balanced = extract_evolution_metrics(_result({
        "factor.two.Rank IC": 0.015,
        "factor.two.day.long_short.annualized_net_return": 0.10,
        "factor.two.day.long_short.sharpe_ratio": 1.0,
        "factor.two.day.long_short.max_drawdown": -0.18,
        "factor.two.day.decile_monotonicity": 0.7,
        "factor.two.day.asset_pricing.ff5.alpha_t_stat": 2.5,
        "factor.two.day.asset_pricing.ff5.alpha_p_value": 0.02,
        "factor.two.day.long_short.average_turnover_per_rebalance": 0.4,
    }))
    assert balanced["evolution_score"] > rank_only["evolution_score"]


def test_trajectory_uses_multidimensional_score_for_success():
    trajectory = StrategyTrajectory(
        trajectory_id="t1", direction_id=0, round_idx=0,
        phase=RoundPhase.ORIGINAL,
        backtest_metrics={"RankIC": -0.01, "evolution_score": 64.0,
                          "evolution_score_coverage": 0.72},
    )
    assert trajectory.get_primary_metric() == -0.01
    assert trajectory.get_evolution_score() == 64.0
    assert trajectory.is_successful()

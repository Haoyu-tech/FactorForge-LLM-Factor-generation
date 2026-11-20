"""Max drawdown must measure from starting wealth 1.0, not from day 1's close.

Expected numbers are computed with exact Fraction arithmetic.
"""
from fractions import Fraction

import pandas as pd
import pytest

from quantaalpha.backtest.long_short_analytics import _summary


def _rows(returns, start="2024-01-01"):
    dates = pd.date_range(start, periods=len(returns), freq="D")
    return [
        {"date": d, "gross_return": r, "net_return": r, "turnover": 0.0,
         "transaction_cost": 0.0, "borrow_cost": 0.0, "positions": 1,
         "is_rebalance": i == 0}
        for i, (d, r) in enumerate(zip(dates, returns))
    ]


def test_drawdown_counts_a_loss_on_the_first_day():
    # Wealth 1.00 -> 0.90 -> 0.855 -> 0.8721; worst fall from the 1.00 start.
    summary = _summary(_rows([-0.10, -0.05, 0.02]), 1)
    expected = Fraction(9, 10) * Fraction(95, 100) - 1  # -0.145
    assert summary["max_drawdown"] == pytest.approx(float(expected), abs=1e-12)


def test_drawdown_after_a_new_high_is_unchanged():
    # Wealth 1.00 -> 1.10 -> 0.99; worst fall is from the 1.10 peak.
    summary = _summary(_rows([0.10, -0.10]), 1)
    expected = Fraction(-1, 10)
    assert summary["max_drawdown"] == pytest.approx(float(expected), abs=1e-12)


def test_drawdown_is_zero_when_wealth_never_falls():
    assert _summary(_rows([0.01, 0.02, 0.0]), 1)["max_drawdown"] == pytest.approx(0.0, abs=1e-12)

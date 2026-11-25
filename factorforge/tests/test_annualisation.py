"""Annualisation must match how many observations a market has per year."""
import math
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from quantaalpha.backtest.long_short_analytics import _summary, default_periods_per_year


def _rows(returns, start="2023-01-01"):
    dates = pd.date_range(start, periods=len(returns), freq="D")
    return [
        {"date": d, "gross_return": r, "net_return": r, "turnover": 0.0,
         "transaction_cost": 0.0, "borrow_cost": 0.0, "positions": 1,
         "is_rebalance": i == 0}
        for i, (d, r) in enumerate(zip(dates, returns))
    ]


def test_periods_per_year_by_market():
    assert default_periods_per_year({"MARKET_MODE": "crypto"}) == 365.25
    assert default_periods_per_year({"MARKET_MODE": "us"}) == 252.0
    assert default_periods_per_year({"MARKET_MODE": "cn"}) == 252.0


def test_one_year_of_daily_crypto_returns_annualises_to_its_own_compounding():
    # 365 calendar days at +0.1%: one non-leap year. 1.001^365 - 1 = 0.440251...
    summary = _summary(_rows([0.001] * 365), 1, periods_per_year=365.0)
    expected = Fraction(1001, 1000) ** 365 - 1
    assert summary["annualized_net_return"] == pytest.approx(float(expected), rel=1e-12)


def test_crypto_default_uses_average_year_length():
    summary = _summary(_rows([0.001] * 365), 1, periods_per_year=default_periods_per_year({"MARKET_MODE": "crypto"}))
    expected = math.exp(365.25 * math.log1p(0.001)) - 1   # 0.440611...
    assert summary["annualized_net_return"] == pytest.approx(expected, rel=1e-12)


def test_sharpe_scales_with_periods_per_year():
    rows = _rows([0.01, -0.005, 0.002, 0.004])
    a = _summary(rows, 1, periods_per_year=252.0)["sharpe_ratio"]
    b = _summary(rows, 1, periods_per_year=365.25)["sharpe_ratio"]
    assert b / a == pytest.approx(np.sqrt(365.25 / 252.0), rel=1e-12)

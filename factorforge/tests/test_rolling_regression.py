"""The vectorized REGBETA/REGRESI fast path must match the row-by-row lstsq loop."""
import numpy as np
import pandas as pd
import pytest

from quantaalpha.factors.coder import function_lib as fl


def _panel(seed: int = 0) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=140)
    rows = []
    # Uneven histories: one instrument shorter than the window, one late listing.
    spans = {"BBB": (0, 140), "AAA": (0, 140), "CCC": (30, 140), "DDD": (120, 140)}
    for inst, (a, b) in spans.items():
        rows += [(d, inst) for d in dates[a:b]]
    index = pd.MultiIndex.from_tuples(sorted(rows), names=["datetime", "instrument"])
    y = pd.Series(rng.normal(0, 0.02, len(index)), index=index)
    y.iloc[::17] = np.nan  # the loop zero-fills NaNs
    x = fl.MEAN(y.fillna(0))
    return y, x


def _loop(y: pd.Series, x: pd.Series, p: int, fn) -> pd.Series:
    parts = [fn(gy, gx, p) for (_, gy), (_, gx) in
             zip(y.fillna(0).groupby("instrument"), x.fillna(0).groupby("instrument"))]
    return pd.concat(parts).sort_index()


@pytest.mark.parametrize("p", [5, 20, 60])
def test_regbeta_matches_loop(p):
    y, x = _panel()
    expected = _loop(y, x, p, fl.rolling_beta)
    got = fl.REGBETA(y, x, p)
    pd.testing.assert_index_equal(got.index, expected.index)
    np.testing.assert_allclose(got.to_numpy(), expected.to_numpy(), rtol=1e-7, atol=1e-10)


@pytest.mark.parametrize("p", [5, 20, 60])
def test_regresi_matches_loop(p):
    y, x = _panel(1)
    expected = _loop(y, x, p, fl.rolling_residuals)
    got = fl.REGRESI(y, x, p)
    pd.testing.assert_index_equal(got.index, expected.index)
    np.testing.assert_allclose(got.to_numpy(), expected.to_numpy(), rtol=1e-7, atol=1e-10)


def test_constant_regressor_matches_lstsq_min_norm():
    y, _ = _panel(2)
    for c in (0.0, 0.003):
        x = pd.Series(c, index=y.index)
        np.testing.assert_allclose(fl.REGBETA(y, x, 10).to_numpy(),
                                   _loop(y, x, 10, fl.rolling_beta).to_numpy(),
                                   rtol=1e-7, atol=1e-12)
        np.testing.assert_allclose(fl.REGRESI(y, x, 10).to_numpy(),
                                   _loop(y, x, 10, fl.rolling_residuals).to_numpy(),
                                   rtol=1e-7, atol=1e-12)

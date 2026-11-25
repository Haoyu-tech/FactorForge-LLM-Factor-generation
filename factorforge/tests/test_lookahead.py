"""Expression operators must not read future values."""
import numpy as np
import pandas as pd
import pytest

from quantaalpha.factors.coder import function_lib as fl


def _panel(values):
    idx = pd.MultiIndex.from_product(
        [pd.date_range("2024-01-01", periods=len(values), freq="D"), ["A"]],
        names=["datetime", "instrument"],
    )
    return pd.DataFrame({"x": values}, index=idx)


@pytest.mark.parametrize("op", [fl.DELTA, fl.TS_PCTCHANGE, fl.DELAY])
def test_negative_periods_are_rejected(op):
    # DELTA(x, -1) would be x_t - x_{t+1}: tomorrow's value inside today's factor.
    with pytest.raises(AssertionError):
        op(_panel([1.0, 2.0, 3.0]), -1)


@pytest.mark.parametrize("op", [fl.DELTA, fl.TS_PCTCHANGE, fl.DELAY])
def test_non_negative_periods_still_work(op):
    out = np.asarray(op(_panel([1.0, 2.0, 4.0]), 1)).ravel()
    assert np.isfinite(out[-1])


def test_percentile_without_window_is_causal():
    base = _panel([1.0, 2.0, 3.0, 4.0])
    later = _panel([1.0, 2.0, 3.0, 100.0])
    a = np.asarray(fl.PERCENTILE(base, 1.0)).ravel()
    b = np.asarray(fl.PERCENTILE(later, 1.0)).ravel()
    # Changing the last value must not change any earlier output.
    np.testing.assert_allclose(a[:3], b[:3])
    np.testing.assert_allclose(a[:3], [1.0, 2.0, 3.0])

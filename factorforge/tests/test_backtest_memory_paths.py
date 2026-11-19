"""Memory-lean backtest preprocessing must reproduce the original semantics."""
import numpy as np
import pandas as pd
import pytest

from quantaalpha.backtest import correlation_pruning as cp
from quantaalpha.backtest import runner as R


def _panel(seed=0, n_dates=40, n_inst=12):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2010-12-01", periods=n_dates)
    insts = [f"S{i:02d}" for i in range(n_inst)]
    rows = [(d, s) for d in dates for s in insts]
    rows.append((pd.Timestamp("2011-03-01"), "S00"))  # a single-stock date
    index = pd.MultiIndex.from_tuples(sorted(rows), names=["datetime", "instrument"])
    feats = pd.DataFrame(rng.normal(size=(len(index), 5)), index=index,
                         columns=[f"f{i}" for i in range(5)])
    feats.iloc[::7, 1] = np.nan
    feats.iloc[3, 2] = np.inf
    feats.iloc[:, 3] = np.round(feats.iloc[:, 3], 1)  # ties
    label = pd.DataFrame({"LABEL0": rng.normal(size=len(index))}, index=index)
    label.iloc[::11, 0] = np.nan
    return feats, label


def _old_preprocess(features_df, label_df):
    """Verbatim logic of the pre-change implementation."""
    combined_df = pd.concat([features_df, label_df], axis=1)
    feature_cols, label_cols = list(features_df.columns), list(label_df.columns)
    combined_df[feature_cols] = combined_df[feature_cols].fillna(0)
    combined_df[feature_cols] = combined_df[feature_cols].replace([np.inf, -np.inf], 0)
    for col in feature_cols:
        combined_df[col] = combined_df.groupby(level=0)[col].transform(
            lambda x: (x.rank(pct=True) - 0.5) if len(x) > 1 else 0)
    combined_df = combined_df.dropna(subset=label_cols)
    for col in label_cols:
        combined_df[col] = combined_df.groupby(level=0)[col].transform(
            lambda x: (x.rank(pct=True) - 0.5) if len(x) > 1 else 0)
    return combined_df


def _build(feats, label):
    runner = object.__new__(R.BacktestRunner)
    runner.config = {"data": {}, "dataset": {"label": "x", "segments": {
        "train": ["2010-12-01", "2010-12-31"], "valid": ["2011-01-01", "2011-01-14"],
        "test": ["2011-01-15", "2011-03-31"]}}}
    runner._compute_label = lambda expr: label
    return runner._create_dataset_with_computed_factors({}, feats.astype(np.float32))


def test_dataset_preprocessing_matches_original():
    feats, label = _panel()
    expected = _old_preprocess(feats.astype(np.float32), label)
    dataset = _build(feats, label)
    got = dataset.handler._data
    pd.testing.assert_index_equal(got.index, expected.index)
    np.testing.assert_allclose(got["feature"].to_numpy(),
                               expected[list(feats.columns)].to_numpy(), atol=1e-6)
    np.testing.assert_allclose(got["label"].to_numpy(),
                               expected[["LABEL0"]].to_numpy(), atol=1e-12)
    assert got["feature"].dtypes.eq(np.float32).all()


@pytest.mark.parametrize("segment", ["train", "valid", "test"])
def test_segment_fetch_matches_mask(segment):
    feats, label = _panel(1)
    dataset = _build(feats, label)
    handler = dataset.handler
    start, end = dataset.segments[segment]
    full = handler._data
    dates = full.index.get_level_values("datetime")
    expected = full.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    got = handler.fetch([start, end], col_set=["feature", "label"])
    pd.testing.assert_frame_equal(got, expected)
    pd.testing.assert_frame_equal(handler.fetch(slice(start, end), col_set="feature"),
                                  expected["feature"])


def test_correlation_pruning_window_filter_matches_original():
    feats, _ = _panel(2, n_dates=120)
    shuffled = feats.swaplevel().sample(frac=1.0, random_state=0)  # unsorted, (inst, date)
    start, end = "2011-01-01", "2011-04-30"

    def old_normalize(frame):
        result = frame.copy()
        result.index = pd.MultiIndex.from_arrays(
            [pd.to_datetime(frame.index.get_level_values(1)),
             frame.index.get_level_values(0).astype(str)], names=["datetime", "instrument"])
        result = result.sort_index()
        d = result.index.get_level_values("datetime")
        return result[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))]

    pd.testing.assert_frame_equal(cp._normalize_index(shuffled, start, end), old_normalize(shuffled))
    corr, months = cp.monthly_cross_sectional_spearman(shuffled, start=start, end=end, min_observations=5)
    assert months == 4 and corr.shape == (5, 5)

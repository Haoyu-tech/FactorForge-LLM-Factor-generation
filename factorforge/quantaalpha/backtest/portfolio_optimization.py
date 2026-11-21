"""MAXSER-PR portfolio construction for out-of-sample factor predictions.

The statistical core is a direct, dependency-light extraction of the user supplied
``maxser-pr-lightgbm.py``.  This adapter deliberately consumes predictions already
produced by QuantaAlpha's expanding-window model; it does not fit a second predictor.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

import numpy as np
import pandas as pd

from .maxser_pr import build_regression_problem, fit_elastic_net_cv

logger = logging.getLogger(__name__)


def _datetime_instrument_index(data: pd.DataFrame) -> pd.DataFrame:
    names = [str(name).lower() if name is not None else "" for name in data.index.names]
    date_pos = names.index("datetime") if "datetime" in names else names.index("date") if "date" in names else 1
    instrument_pos = 1 - date_pos
    result = data.copy()
    result.index = pd.MultiIndex.from_arrays(
        [pd.to_datetime(data.index.get_level_values(date_pos)), data.index.get_level_values(instrument_pos).astype(str)],
        names=["datetime", "instrument"],
    )
    return result.sort_index()


SAMPLE_WINDOW_SESSIONS = 756
MIN_DAILY_OBSERVATIONS = 250
MIN_NAMES = 50
# Estimation needs this many window sessions with a signal in force.
MIN_SIGNAL_SESSIONS = 60
# A monthly snapshot stays in force for at most this many sessions.
SIGNAL_FFILL_SESSIONS = 25
CV_ALPHA_GRID = (0.0, 0.02, 0.05, 0.10)
CV_LAMBDA_COUNT = 12
CV_FOLDS = 3


def label_execution_lag(label_expression: object) -> int:
    """Sessions between the signal close and the first return the label pays.

    ``Ref($ret_total, -1)`` pays the return over (t, t+1]: lag 0.
    ``Ref($ret_total, -2)`` and ``Ref($close, -2) / Ref($close, -1) - 1`` pay
    (t+1, t+2]: lag 1, i.e. the trade happens at the close of t+1.
    """
    offsets = [int(value) for value in re.findall(r"Ref\(\s*\$\w+\s*,\s*-(\d+)\s*\)", str(label_expression or ""))]
    return max(max(offsets) - 1, 0) if offsets else 0


def snap_to_sessions(signal: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """Move each signal date to the last trading session on or before it.

    Calendar month-end dates (as in the JKP/Kelly panel) are often weekends
    or holidays and would otherwise match no trading day.
    """
    dates = pd.DatetimeIndex(signal.index.get_level_values("datetime"))
    positions = sessions.searchsorted(dates, side="right") - 1
    keep = positions >= 0
    snapped = signal[keep].copy()
    snapped.index = pd.MultiIndex.from_arrays(
        [sessions[positions[keep]], signal.index.get_level_values("instrument")[keep]],
        names=["datetime", "instrument"],
    )
    # Input is date-sorted, so "last" keeps the latest original date.
    return snapped[~snapped.index.duplicated(keep="last")].sort_index()


def signal_in_force(scores: pd.DataFrame, lag: int) -> pd.DataFrame:
    """Score that forecasts the return on each session.

    The return on session t is paid to a position traded at the close of
    t-1, which used the latest snapshot at or before session t-1-lag.
    """
    return scores.ffill(limit=SIGNAL_FFILL_SESSIONS).shift(1 + int(lag))


def signal_return_slope(returns: np.ndarray, signals: np.ndarray, min_names: int = 20) -> tuple[float, int]:
    """Mean daily cross-sectional OLS slope of returns on signals.

    Converts a score in any unit (rank, monthly forecast) into an expected
    daily return: E[r_i,t] - mean_t = slope * (s_i,t - mean_t).
    """
    mask = np.isfinite(returns) & np.isfinite(signals)
    x = np.where(mask, signals, np.nan)
    y = np.where(mask, returns, np.nan)
    counts = mask.sum(axis=1)
    usable = counts >= min_names
    if not usable.any():
        return float("nan"), 0
    with np.errstate(invalid="ignore", divide="ignore"):
        x = x[usable] - np.nanmean(x[usable], axis=1, keepdims=True)
        y = y[usable] - np.nanmean(y[usable], axis=1, keepdims=True)
        variance = np.nansum(x * x, axis=1)
        slope = np.nansum(x * y, axis=1) / variance
    slope = slope[np.isfinite(slope) & (variance > 0)]
    return (float(slope.mean()), int(slope.size)) if slope.size else (float("nan"), 0)


def _estimate_weights(returns, in_force, current, end_pos):
    """Fit MAXSER-PR at session ``end_pos``; return (weights, slope, sessions) or a skip reason."""
    window = slice(max(0, end_pos - SAMPLE_WINDOW_SESSIONS + 1), end_pos + 1)
    history = returns.iloc[window]
    eligible = [
        name for name in current.index
        if name in history.columns and history[name].notna().sum() >= MIN_DAILY_OBSERVATIONS
    ]
    if len(eligible) < MIN_NAMES:
        return "too_few_names"
    signals = in_force.iloc[window].reindex(columns=eligible)
    available = signals.notna().any(axis=1).to_numpy()
    if int(available.sum()) < MIN_SIGNAL_SESSIONS:
        return "insufficient_signal_history"
    R = history[eligible].to_numpy(dtype=float)[available]
    S_raw = signals.to_numpy(dtype=float)[available]
    slope, _ = signal_return_slope(R, S_raw)
    if not np.isfinite(slope) or slope <= 0.0:
        # The model's ranking has not paid in this window; hold rather than
        # flip the forecast sign.
        return "nonpositive_signal_slope"
    with np.errstate(invalid="ignore"):
        S = slope * (S_raw - np.nanmean(S_raw, axis=1, keepdims=True))
    S = np.nan_to_num(S, nan=0.0)
    score_now = current.reindex(eligible).to_numpy(dtype=float)
    mu = slope * (score_now - score_now.mean())
    problem = build_regression_problem(np.nan_to_num(R, nan=0.0), S, mu)
    # The supplied research script uses an exhaustive 11 alpha x 100 lambda
    # x 10-fold grid. Repeating that for every test month takes hours on an
    # interactive workstation. This keeps the same MAXSER-PR/POET/positive
    # elastic-net estimator with a deterministic 4 x 12 x 3 production grid.
    values = (
        np.zeros(len(eligible), dtype=float)
        if problem["status"] == "zero"
        else fit_elastic_net_cv(
            problem["X"], problem["Y"],
            alpha_grid=np.asarray(CV_ALPHA_GRID), n_lambda=CV_LAMBDA_COUNT, n_folds=CV_FOLDS,
        )
    )
    weights = pd.Series(values, index=eligible)
    if not np.isfinite(weights).all() or abs(float(weights.sum())) > 1e-7:
        raise ValueError("optimizer returned invalid zero-investment weights")
    return weights, slope, int(available.sum())


def calculate_maxser_pr_analytics(pred: pd.Series, config: Dict) -> tuple[Dict, Dict]:
    """Monthly zero-investment MAXSER-PR portfolio without look-ahead.

    * Signal dates are snapped to the last trading session on or before them.
    * The portfolio formed from the snapshot at session d trades at the close
      of d + lag (lag from the label, or ``long_short.execution_lag_days``).
    * Estimation uses the 756 sessions up to d, restricted to sessions with a
      signal in force; signals and the synthetic mean are put in daily-return
      units with the window's mean cross-sectional slope of returns on the
      signal.
    * Weights drift between rebalances; turnover is charged from the drifted
      weights. A month that cannot be re-optimized keeps the previous book.
    """
    from qlib.data import D
    from quantaalpha.backtest.long_short_analytics import _summary as summarize, drift_weights, held_returns
    from quantaalpha.market.profile import load_held_returns

    signal = pred.iloc[:, 0] if isinstance(pred, pd.DataFrame) else pred
    signal = signal.rename("score").replace([np.inf, -np.inf], np.nan).dropna()
    signal = _datetime_instrument_index(signal.to_frame())["score"]

    bt = config["backtest"]["backtest"]
    ls_config = config.get("backtest", {}).get("long_short", {})
    lag = (
        int(ls_config["execution_lag_days"]) if "execution_lag_days" in ls_config
        else label_execution_lag(config.get("dataset", {}).get("label"))
    )
    start = pd.Timestamp(bt["start_time"])
    end = pd.Timestamp(bt["end_time"])
    history_start = start - pd.Timedelta(days=1200)
    sessions = pd.DatetimeIndex(D.calendar(start_time=history_start, end_time=end, freq="day"))
    raw = load_held_returns(D, config["data"]["market"], "$ret_total", history_start, end)
    raw.columns = ["return"]
    raw = _datetime_instrument_index(raw)
    returns = raw["return"].unstack("instrument").reindex(sessions)

    signal = snap_to_sessions(signal, sessions)
    scores = signal.unstack("instrument").reindex(index=sessions)
    in_force = signal_in_force(scores, lag).reindex(columns=returns.columns)
    signal_sessions = sessions[scores.notna().any(axis=1).to_numpy()]
    rebalance_sessions = pd.Series(signal_sessions, index=signal_sessions.to_period("M")).groupby(level=0).max()

    cost_rate = float(ls_config.get("transaction_cost", 0.0005))
    borrow_rate = float(ls_config.get("short_borrow_rate", 0.0)) / 252.0
    trades: Dict[int, pd.Series] = {}
    skipped: Dict[str, int] = {}
    slopes: List[float] = []
    signal_session_counts: List[int] = []
    optimized = failed = 0
    gross_exposure: List[float] = []
    total_months = len(rebalance_sessions)
    for month_number, (period, session) in enumerate(rebalance_sessions.items(), start=1):
        print(f"[4/4] MAXSER-PR 组合优化 {month_number}/{total_months}: {period}", flush=True)
        position = int(sessions.get_loc(session))
        trade_position = position + lag
        if trade_position + 1 >= len(sessions) or sessions[trade_position + 1] > end:
            continue
        current = scores.iloc[position].dropna()
        try:
            outcome = _estimate_weights(returns, in_force, current, position)
        except Exception as exc:
            failed += 1
            logger.warning("MAXSER-PR failed for %s: %s", period, exc)
            continue
        if isinstance(outcome, str):
            skipped[outcome] = skipped.get(outcome, 0) + 1
            logger.warning("MAXSER-PR skipped %s: %s", period, outcome)
            continue
        weights, slope, used_sessions = outcome
        optimized += 1
        slopes.append(slope)
        signal_session_counts.append(used_sessions)
        gross_exposure.append(float(weights.abs().sum()))
        trades[trade_position] = weights

    rows: List[Dict] = []
    if trades:
        book = pd.Series(dtype=float)
        first = min(trades) + 1
        for t in range(first, len(sessions)):
            date = sessions[t]
            if date > end:
                break
            turnover, rebalanced = 0.0, (t - 1) in trades
            if rebalanced:
                target = trades[t - 1]
                turnover = float(target.subtract(book, fill_value=0.0).abs().sum())
                book = target
            if book.empty:
                continue
            day, missing = held_returns(book, returns.iloc[t])
            gross_ret = float((book * day).sum())
            if date < start:
                book = drift_weights(book, day, gross_ret)
                continue
            transaction_cost = turnover * cost_rate
            exposure = float(book.abs().sum())
            borrow_cost = float(book[book < 0].abs().sum()) * borrow_rate
            rows.append({
                "date": pd.Timestamp(date), "gross_return": gross_ret,
                "net_return": gross_ret - transaction_cost - borrow_cost,
                "turnover": turnover, "transaction_cost": transaction_cost,
                "borrow_cost": borrow_cost, "positions": int((book != 0).sum()),
                "is_rebalance": rebalanced,
                "missing_return_exposure": missing / exposure if exposure > 0 else 0.0,
            })
            book = drift_weights(book, day, gross_ret)

    if not rows:
        raise ValueError("MAXSER-PR did not produce any investable out-of-sample month")
    diagnostics = {
        "enabled": True,
        "method": "MAXSER-PR (POET + positive elastic-net)",
        "rebalance": "monthly",
        "signal_alignment": "last trading session on or before each signal date",
        "execution_lag_days": lag,
        "signal_scaling": "mean daily cross-sectional OLS slope of returns on the signal (daily return units)",
        "average_signal_slope": float(np.mean(slopes)) if slopes else 0.0,
        "average_signal_sessions": float(np.mean(signal_session_counts)) if signal_session_counts else 0.0,
        "sample_window_days": SAMPLE_WINDOW_SESSIONS,
        "minimum_signal_sessions": MIN_SIGNAL_SESSIONS,
        "minimum_daily_observations": MIN_DAILY_OBSERVATIONS,
        "minimum_names": MIN_NAMES,
        "target_annualized_volatility": 0.04,
        "optimized_months": optimized,
        "failed_months": failed,
        "skipped_months": skipped,
        "skip_policy": "keep the previous portfolio (drifting) until the next successful rebalance",
        "average_gross_exposure": float(np.mean(gross_exposure)) if gross_exposure else 0.0,
        "net_exposure_constraint": 0.0,
        "cv_alpha_grid": list(CV_ALPHA_GRID),
        "cv_lambda_count": CV_LAMBDA_COUNT,
        "cv_folds": CV_FOLDS,
    }
    result = summarize(rows, optimized, 252.0)
    result["portfolio_method"] = diagnostics["method"]
    return result, diagnostics

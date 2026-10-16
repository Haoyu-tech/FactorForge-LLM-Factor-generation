"""MAXSER-PR portfolio construction for out-of-sample factor predictions.

The statistical core is a direct, dependency-light extraction of the user supplied
``maxser-pr-lightgbm.py``.  This adapter deliberately consumes predictions already
produced by QuantaAlpha's expanding-window model; it does not fit a second predictor.
"""

from __future__ import annotations

import logging
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


def _summary(rows: List[Dict]) -> Dict:
    frame = pd.DataFrame(rows).set_index("date").sort_index()
    net = frame["net_return"].clip(lower=-0.999999)
    gross = frame["gross_return"].clip(lower=-0.999999)
    net_equity = (1.0 + net).cumprod()
    gross_equity = (1.0 + gross).cumprod()
    periods = len(frame)
    annualized = lambda curve: float(curve.iloc[-1] ** (252.0 / periods) - 1.0)
    vol = float(net.std(ddof=1) * np.sqrt(252.0)) if periods > 1 else 0.0
    sharpe = float(net.mean() / net.std(ddof=1) * np.sqrt(252.0)) if periods > 1 and net.std(ddof=1) > 0 else 0.0
    drawdown = net_equity / net_equity.cummax() - 1.0
    return {
        "annualized_gross_return": annualized(gross_equity),
        "annualized_net_return": annualized(net_equity),
        "total_net_return": float(net_equity.iloc[-1] - 1.0),
        "annualized_volatility": vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": float(drawdown.min()),
        "average_daily_turnover": float(frame["turnover"].mean()),
        "annualized_turnover": float(frame["turnover"].mean() * 252.0),
        "total_transaction_cost": float(frame["transaction_cost"].sum()),
        "total_borrow_cost": float(frame["borrow_cost"].sum()),
        "average_positions": float(frame["positions"].mean()),
        "daily_net_returns": [{"date": d.strftime("%Y-%m-%d"), "value": float(v)} for d, v in net.items()],
        "curve": [{"date": d.strftime("%Y-%m-%d"), "value": float(v - 1.0)} for d, v in net_equity.items()],
    }


def calculate_maxser_pr_analytics(pred: pd.Series, config: Dict) -> tuple[Dict, Dict]:
    """Create a monthly zero-investment MAXSER-PR portfolio without look-ahead."""
    from qlib.data import D

    signal = pred.iloc[:, 0] if isinstance(pred, pd.DataFrame) else pred
    signal = signal.rename("score").replace([np.inf, -np.inf], np.nan).dropna()
    if signal.index.names != ["datetime", "instrument"]:
        signal.index = signal.index.set_names(["datetime", "instrument"])

    bt = config["backtest"]["backtest"]
    instruments = D.instruments(config["data"]["market"])
    start = pd.Timestamp(bt["start_time"])
    end = pd.Timestamp(bt["end_time"])
    history_start = start - pd.Timedelta(days=1200)
    raw = D.features(instruments, ["$ret_total"], start_time=history_start, end_time=end, freq="day")
    raw.columns = ["return"]
    raw = _datetime_instrument_index(raw)
    returns = raw["return"].unstack("instrument").sort_index()

    scores = signal.unstack("instrument").sort_index()
    # One signal snapshot per month; the last available score of month t is held in month t+1.
    snapshots = [(m, g.iloc[-1].dropna()) for m, g in scores.groupby(scores.index.to_period("M"))]
    cost_rate = float(config.get("backtest", {}).get("long_short", {}).get("transaction_cost", 0.0005))
    borrow_rate = float(config.get("backtest", {}).get("long_short", {}).get("short_borrow_rate", 0.0)) / 252.0
    previous = pd.Series(dtype=float)
    rows: List[Dict] = []
    optimized = failed = 0
    gross_exposure: List[float] = []

    total_months = len(snapshots)
    for month_number, (period, current) in enumerate(snapshots, start=1):
        print(
            f"[4/4] MAXSER-PR 组合优化 {month_number}/{total_months}: {period}",
            flush=True,
        )
        rebalance_date = scores.loc[scores.index.to_period("M") == period].index[-1]
        target_period = period + 1
        target_dates = returns.index[(returns.index.to_period("M") == target_period) & (returns.index >= start) & (returns.index <= end)]
        if not len(target_dates):
            continue
        window = returns.loc[returns.index <= rebalance_date].tail(756)
        eligible = [c for c in current.index if c in window.columns and window[c].notna().sum() >= 250]
        if len(eligible) < 50:
            failed += 1
            logger.warning("MAXSER-PR skipped %s: only %d eligible names", period, len(eligible))
            continue
        R = window[eligible].fillna(0.0).to_numpy(dtype=float)
        hist = scores.reindex(window.index).ffill().fillna(0.0)
        S = hist.reindex(columns=eligible, fill_value=0.0).to_numpy(dtype=float)
        mu = current.reindex(eligible).to_numpy(dtype=float) * (12.0 / 252.0)
        try:
            problem = build_regression_problem(R, S, mu)
            # The supplied research script uses an exhaustive 11 alpha x 100
            # lambda x 10-fold grid. Repeating that for every test month takes
            # hours on an interactive workstation. This keeps the same
            # MAXSER-PR/POET/positive-elastic-net estimator while using a
            # deterministic production grid (4 x 12 x 3 = 144 candidates).
            values = (
                np.zeros(len(eligible), dtype=float)
                if problem["status"] == "zero"
                else fit_elastic_net_cv(
                    problem["X"], problem["Y"],
                    alpha_grid=np.asarray([0.0, 0.02, 0.05, 0.10]),
                    n_lambda=12,
                    n_folds=3,
                )
            )
            weights = pd.Series(values, index=eligible)
            if not np.isfinite(weights).all() or abs(float(weights.sum())) > 1e-7:
                raise ValueError("optimizer returned invalid zero-investment weights")
        except Exception as exc:
            failed += 1
            logger.warning("MAXSER-PR failed for %s: %s", period, exc)
            continue
        optimized += 1
        gross_exposure.append(float(weights.abs().sum()))
        delta = weights.subtract(previous, fill_value=0.0)
        rebalance_turnover = float(delta.abs().sum())
        for pos, date in enumerate(target_dates):
            day = returns.loc[date].reindex(weights.index)
            gross_ret = float((weights * day.fillna(0.0)).sum())
            turnover = rebalance_turnover if pos == 0 else 0.0
            transaction_cost = turnover * cost_rate
            borrow_cost = float(weights[weights < 0].abs().sum()) * borrow_rate
            rows.append({
                "date": pd.Timestamp(date), "gross_return": gross_ret,
                "net_return": gross_ret - transaction_cost - borrow_cost,
                "turnover": turnover, "transaction_cost": transaction_cost,
                "borrow_cost": borrow_cost, "positions": int((weights != 0).sum()),
            })
        previous = weights

    if not rows:
        raise ValueError("MAXSER-PR did not produce any investable out-of-sample month")
    diagnostics = {
        "enabled": True,
        "method": "MAXSER-PR (POET + positive elastic-net)",
        "rebalance": "monthly",
        "sample_window_days": 756,
        "minimum_daily_observations": 250,
        "minimum_names": 50,
        "target_annualized_volatility": 0.04,
        "optimized_months": optimized,
        "failed_months": failed,
        "average_gross_exposure": float(np.mean(gross_exposure)) if gross_exposure else 0.0,
        "net_exposure_constraint": 0.0,
        "cv_alpha_grid": [0.0, 0.02, 0.05, 0.10],
        "cv_lambda_count": 12,
        "cv_folds": 3,
    }
    result = _summary(rows)
    result["portfolio_method"] = diagnostics["method"]
    return result, diagnostics

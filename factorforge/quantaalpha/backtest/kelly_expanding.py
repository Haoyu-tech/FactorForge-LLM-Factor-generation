"""Expanding-window ML backtest for the JKP/Kelly 153 factors."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd


ID_COLUMNS = {"permno", "eom", "ret_exc_lead1m", "ret_exc", "me"}


def _finite(value: float) -> float:
    return float(value) if np.isfinite(value) else 0.0


def _summary(rows: list[dict], periods_per_year: float = 12.0) -> dict:
    if not rows:
        return {}
    frame = pd.DataFrame(rows).set_index("date").sort_index()
    gross = frame["gross_return"].clip(lower=-0.999999)
    net = frame["net_return"].clip(lower=-0.999999)
    gross_curve = (1.0 + gross).cumprod()
    net_curve = (1.0 + net).cumprod()
    years = max(len(frame) / periods_per_year, 1.0 / periods_per_year)
    annual_gross = float(gross_curve.iloc[-1] ** (1.0 / years) - 1.0)
    annual_net = float(net_curve.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(net.std(ddof=1) * math.sqrt(periods_per_year)) if len(net) > 1 else 0.0
    sharpe = float(net.mean() / net.std(ddof=1) * math.sqrt(periods_per_year)) if len(net) > 1 and net.std(ddof=1) > 0 else 0.0
    drawdown = net_curve / net_curve.cummax() - 1.0
    turnover = frame["turnover"]
    return {
        "annualized_gross_return": _finite(annual_gross),
        "annualized_net_return": _finite(annual_net),
        "total_net_return": _finite(net_curve.iloc[-1] - 1.0),
        "annualized_volatility": _finite(volatility),
        "sharpe_ratio": _finite(sharpe),
        "max_drawdown": _finite(drawdown.min()),
        "average_daily_turnover": _finite(turnover.mean()),
        "average_turnover_per_rebalance": _finite(turnover.mean()),
        "annualized_turnover": _finite(turnover.mean() * periods_per_year),
        "total_transaction_cost": _finite(frame["transaction_cost"].sum()),
        "total_borrow_cost": 0.0,
        "average_positions": _finite(frame["positions"].mean()),
        "rebalance_count": int(len(frame)),
        "curve": [
            {"date": date.strftime("%Y-%m-%d"), "value": _finite(value - 1.0)}
            for date, value in net_curve.items()
        ],
        "daily_net_returns": [
            {"date": date.strftime("%Y-%m-%d"), "value": _finite(value)}
            for date, value in net.items()
        ],
    }


def portfolio_analytics(
    predictions: pd.DataFrame,
    quantile: float = 0.10,
    min_positions: int = 20,
    transaction_cost: float = 0.0005,
) -> tuple[dict, dict]:
    names = ["long", "short", "long_short", *[f"group_{number}" for number in range(1, 11)]]
    previous = {name: pd.Series(dtype=float) for name in names}
    rows = {name: [] for name in names}
    for date, group in predictions.groupby("eom", sort=True):
        group = group.replace([np.inf, -np.inf], np.nan).dropna(subset=["score", "ret_exc_lead1m"])
        group = group.sort_values("score").set_index("permno")
        count = min(max(min_positions, int(math.ceil(len(group) * quantile))), len(group) // 2)
        if count < 1:
            continue
        low, high = group.iloc[:count], group.iloc[-count:]
        weights = {
            "long": pd.Series(1.0 / count, index=high.index),
            "short": pd.Series(-1.0 / count, index=low.index),
        }
        weights["long_short"] = pd.concat([weights["long"] * 0.5, weights["short"] * 0.5])
        for number, members in enumerate(np.array_split(group.index.to_numpy(), 10), start=1):
            if len(members):
                weights[f"group_{number}"] = pd.Series(1.0 / len(members), index=members)
        realized = group["ret_exc_lead1m"]
        for name, weight in weights.items():
            turnover = float(weight.subtract(previous[name], fill_value=0.0).abs().sum())
            gross = float((weight * realized.reindex(weight.index).fillna(0.0)).sum())
            cost = turnover * transaction_cost
            rows[name].append({
                "date": pd.Timestamp(date),
                "gross_return": gross,
                "net_return": gross - cost,
                "turnover": turnover,
                "transaction_cost": cost,
                "positions": len(weight),
            })
            previous[name] = weight.copy()

    portfolios = {name: _summary(rows[name]) for name in ("long", "short", "long_short")}
    deciles = {name: _summary(rows[name]) for name in (f"group_{i}" for i in range(1, 11))}
    return portfolios, deciles


def ic_metrics(predictions: pd.DataFrame) -> dict:
    pearson, spearman = [], []
    for _, group in predictions.groupby("eom", sort=True):
        group = group.replace([np.inf, -np.inf], np.nan).dropna(subset=["score", "ret_exc_lead1m"])
        if len(group) < 3 or group["score"].nunique() < 2 or group["ret_exc_lead1m"].nunique() < 2:
            continue
        pearson.append(group["score"].corr(group["ret_exc_lead1m"], method="pearson"))
        spearman.append(group["score"].corr(group["ret_exc_lead1m"], method="spearman"))

    def pair(values: list[float]) -> tuple[float, float]:
        series = pd.Series(values, dtype=float).dropna()
        if series.empty:
            return 0.0, 0.0
        mean = float(series.mean())
        std = float(series.std(ddof=1)) if len(series) > 1 else 0.0
        return mean, mean / std if std > 0 else 0.0

    ic, icir = pair(pearson)
    rank_ic, rank_icir = pair(spearman)
    return {"IC": ic, "ICIR": icir, "Rank IC": rank_ic, "Rank ICIR": rank_icir}


def cross_sectional_rank(frame: pd.DataFrame, factors: list[str]) -> pd.DataFrame:
    ranked = frame.groupby("eom", sort=False)[factors].rank(method="average", pct=True)
    return (ranked * 2.0 - 1.0).astype("float32")


def run_expanding_backtest(
    panel_path: str | Path,
    output_dir: str | Path,
    missing_threshold: float = 0.20,
    model_type: str = "lightgbm",
    retrain_months: int = 12,
    min_train_years: int = 10,
    train_start: str = "1987-01-01",
    train_end: str = "2010-12-31",
    valid_start: str = "2011-01-01",
    valid_end: str = "2014-12-31",
    test_start: str = "2015-01-01",
    test_end: str = "2025-12-31",
    portfolio_mode: str = "long_short",
    transaction_cost: float = 0.0005,
    portfolio_optimization: bool = False,
    correlation_pruning: bool = False,
    correlation_threshold: float = 0.85,
) -> Path:
    import lightgbm as lgb
    from lightgbm import LGBMRegressor
    from sklearn.cross_decomposition import PLSRegression
    from sklearn.linear_model import Lasso
    from sklearn.metrics import mean_squared_error

    if model_type not in {"lightgbm", "pls5", "lasso"}:
        raise ValueError(f"Unsupported Kelly model: {model_type}")
    started = time.time()
    panel_path = Path(panel_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print("[1/4] 加载 WRDS Kelly 153 因子与历史 S&P 500 月度面板", flush=True)
    panel = pd.read_parquet(panel_path)
    panel["eom"] = pd.to_datetime(panel["eom"], errors="coerce")
    panel["permno"] = pd.to_numeric(panel["permno"], errors="coerce").astype("Int64")
    panel = panel.dropna(subset=["eom", "permno"]).sort_values(["eom", "permno"]).reset_index(drop=True)
    factors = [column for column in panel.columns if column not in ID_COLUMNS]
    if len(factors) != 153:
        raise ValueError(f"Expected 153 Kelly factors, found {len(factors)}")
    train_start_ts = pd.Timestamp(train_start)
    train_end_ts = pd.Timestamp(train_end)
    valid_start_ts = pd.Timestamp(valid_start)
    valid_end_ts = pd.Timestamp(valid_end)
    test_start_ts = pd.Timestamp(test_start)
    test_end_ts = pd.Timestamp(test_end)
    if not (train_start_ts <= train_end_ts < valid_start_ts <= valid_end_ts < test_start_ts <= test_end_ts):
        raise ValueError(
            "Expected ordered, non-overlapping train/valid/test segments, got "
            f"train={train_start}..{train_end}, valid={valid_start}..{valid_end}, "
            f"test={test_start}..{test_end}"
        )
    panel = panel[(panel["eom"] >= train_start_ts) & (panel["eom"] <= test_end_ts)]
    test_dates = pd.DatetimeIndex(
        panel.loc[
            (panel["eom"] >= test_start_ts) & (panel["eom"] <= test_end_ts),
            "eom",
        ].drop_duplicates().sort_values()
    )
    if test_dates.empty:
        raise ValueError("No Kelly observations overlap the requested test interval")
    earliest_prediction = panel["eom"].min() + pd.DateOffset(years=min_train_years)
    test_dates = test_dates[test_dates >= earliest_prediction]
    if test_dates.empty:
        raise ValueError("Test interval starts before the minimum expanding training history is available")

    print("[2/4] 月度横截面排序标准化（仅使用当月可见特征）", flush=True)
    ranked = cross_sectional_rank(panel, factors)
    # Missing characteristics are filled with the same-month cross-sectional
    # median after ranking. With ranks scaled to [-1, 1], a fully missing
    # factor-month falls back to the neutral value 0. This uses no returns and
    # no observations from future months.
    cross_sectional_medians = ranked.groupby(panel["eom"], sort=False).transform("median")
    ranked = ranked.fillna(cross_sectional_medians).fillna(0.0).astype("float32")
    label = pd.to_numeric(panel["ret_exc_lead1m"], errors="coerce").astype("float32")

    # The validation segment is used only to choose model complexity. Reported
    # IC and portfolio returns remain strictly inside the configured test set.
    tune_train_mask = (
        (panel["eom"] >= train_start_ts)
        & (panel["eom"] <= train_end_ts)
        & label.notna()
    )
    tune_valid_mask = (
        (panel["eom"] >= valid_start_ts)
        & (panel["eom"] <= valid_end_ts)
        & label.notna()
    )
    if not tune_train_mask.any() or not tune_valid_mask.any():
        raise ValueError("Configured train or validation segment has no usable Kelly observations")
    tune_missing = panel.loc[tune_train_mask, factors].isna().mean()
    tune_factors = tune_missing[tune_missing <= missing_threshold].index.tolist()
    if not tune_factors:
        raise ValueError("No Kelly factors meet the missing threshold in the configured training set")

    correlation_report = {"enabled": False}
    correlation_keep = set(factors)
    if correlation_pruning and len(tune_factors) > 1:
        from quantaalpha.backtest.correlation_pruning import (
            prune_correlated_factors, validation_rank_ic_scores,
        )
        keys = panel.loc[tune_valid_mask, ["eom", "permno"]]
        validation_factors = ranked.loc[tune_valid_mask, tune_factors].copy()
        validation_factors.index = pd.MultiIndex.from_arrays(
            [keys["eom"], keys["permno"].astype(str)],
            names=["datetime", "instrument"],
        )
        validation_target = label.loc[tune_valid_mask].copy()
        validation_target.index = validation_factors.index
        representative_scores = validation_rank_ic_scores(
            validation_factors, validation_target,
            start=valid_start, end=valid_end,
        )
        validation_factors, correlation_report = prune_correlated_factors(
            validation_factors,
            start=valid_start,
            end=valid_end,
            threshold=correlation_threshold,
            scores=representative_scores,
        )
        tune_factors = list(validation_factors.columns)
        correlation_keep = set(tune_factors)
        correlation_report["selection_score"] = "absolute_mean_validation_rank_ic"
        correlation_report["scope"] = "kelly_factor_columns"
        print(
            f"[2/4] Correlation pruning: {correlation_report['before_count']} -> "
            f"{correlation_report['after_count']} factors "
            f"(|Spearman| >= {correlation_threshold:.2f})",
            flush=True,
        )

    def winsorized_target(mask: pd.Series) -> pd.Series:
        target = label.loc[mask].copy()
        dates = panel.loc[mask, "eom"]
        lower = target.groupby(dates).transform(lambda values: values.quantile(0.01))
        upper = target.groupby(dates).transform(lambda values: values.quantile(0.99))
        return target.clip(lower=lower, upper=upper)

    def imputed_pair(
        train_frame: pd.DataFrame,
        other_frame: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        # ranked was already imputed independently within each month above.
        return train_frame.astype("float32"), other_frame.astype("float32")

    training_started = time.time()
    validation_detail: dict[str, float | int | str] = {"model": model_type}
    if model_type == "lightgbm":
        tuning_model = LGBMRegressor(
            objective="regression",
            n_estimators=600,
            learning_rate=0.035,
            num_leaves=31,
            max_depth=-1,
            min_child_samples=100,
            subsample=0.85,
            colsample_bytree=0.80,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            verbosity=-1,
        )
        tuning_model.fit(
            ranked.loc[tune_train_mask, tune_factors],
            winsorized_target(tune_train_mask),
            eval_set=[(
                ranked.loc[tune_valid_mask, tune_factors],
                winsorized_target(tune_valid_mask),
            )],
            eval_metric="l2",
            callbacks=[lgb.early_stopping(40, verbose=False)],
        )
        best_iterations = int(tuning_model.best_iteration_ or 180)
        validation_detail["best_iterations"] = best_iterations
    elif model_type == "lasso":
        tune_x, valid_x = imputed_pair(
            ranked.loc[tune_train_mask, tune_factors],
            ranked.loc[tune_valid_mask, tune_factors],
        )
        tune_y = winsorized_target(tune_train_mask)
        valid_y = winsorized_target(tune_valid_mask)
        best_alpha, best_loss = 0.001, float("inf")
        for alpha in (0.00001, 0.00003, 0.0001, 0.0003, 0.001, 0.003, 0.01):
            candidate = Lasso(alpha=alpha, max_iter=5000, tol=1e-4, selection="cyclic")
            candidate.fit(tune_x, tune_y)
            loss = float(mean_squared_error(valid_y, candidate.predict(valid_x)))
            if loss < best_loss:
                best_alpha, best_loss = alpha, loss
        validation_detail.update(best_alpha=best_alpha, validation_mse=best_loss)
    else:
        tune_x, valid_x = imputed_pair(
            ranked.loc[tune_train_mask, tune_factors],
            ranked.loc[tune_valid_mask, tune_factors],
        )
        components = min(5, len(tune_factors))
        candidate = PLSRegression(n_components=components, scale=False, max_iter=500)
        candidate.fit(tune_x, winsorized_target(tune_train_mask))
        loss = float(mean_squared_error(
            winsorized_target(tune_valid_mask),
            candidate.predict(valid_x).reshape(-1),
        ))
        validation_detail.update(n_components=components, validation_mse=loss)

    print(
        f"[2/4] 验证完成: model={model_type}, detail={validation_detail} "
        f"(train={int(tune_train_mask.sum()):,}, valid={int(tune_valid_mask.sum()):,}, "
        f"factors={len(tune_factors)})",
        flush=True,
    )

    predictions: list[pd.DataFrame] = []
    selected_counts: list[int] = []
    selected_last: list[str] = []
    for offset in range(0, len(test_dates), retrain_months):
        predict_dates = test_dates[offset: offset + retrain_months]
        refit_date = predict_dates[0]
        train_mask = (panel["eom"] < refit_date) & label.notna()
        predict_mask = panel["eom"].isin(predict_dates)
        train_rows = int(train_mask.sum())
        if train_rows == 0 or not predict_mask.any():
            continue
        training_missing = panel.loc[train_mask, factors].isna().mean()
        selected = [
            name for name in training_missing[training_missing <= missing_threshold].index
            if name in correlation_keep
        ]
        if not selected:
            raise ValueError(
                f"No Kelly factors meet missing threshold {missing_threshold:.0%} before {refit_date.date()}"
            )
        selected_counts.append(len(selected))
        selected_last = selected
        x_train = ranked.loc[train_mask, selected]
        y_train = label.loc[train_mask]
        # Winsorize returns within each historical month without using future months.
        y_train = winsorized_target(train_mask)

        predict_x = ranked.loc[predict_mask, selected]
        if model_type == "lightgbm":
            model = LGBMRegressor(
                objective="regression",
                n_estimators=int(validation_detail["best_iterations"]),
                learning_rate=0.035,
                num_leaves=31,
                max_depth=-1,
                min_child_samples=100,
                subsample=0.85,
                colsample_bytree=0.80,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                verbosity=-1,
            )
            model.fit(x_train, y_train)
            score = model.predict(predict_x)
        elif model_type == "lasso":
            fit_x, predict_x = imputed_pair(x_train, predict_x)
            model = Lasso(
                alpha=float(validation_detail["best_alpha"]),
                max_iter=5000,
                tol=1e-4,
                selection="cyclic",
            )
            model.fit(fit_x, y_train)
            score = model.predict(predict_x)
        else:
            fit_x, predict_x = imputed_pair(x_train, predict_x)
            model = PLSRegression(
                n_components=min(5, len(selected)),
                scale=False,
                max_iter=500,
            )
            model.fit(fit_x, y_train)
            score = model.predict(predict_x).reshape(-1)
        block = panel.loc[predict_mask, ["eom", "permno", "ret_exc_lead1m"]].copy()
        block["score"] = score
        predictions.append(block)
        print(
            f"[3/4] Expanding refit {refit_date.date()}: "
            f"train={train_rows:,}, factors={len(selected)}, predict_months={len(predict_dates)}",
            flush=True,
        )

    if not predictions:
        raise RuntimeError("Expanding window produced no predictions")
    prediction_frame = pd.concat(predictions, ignore_index=True).sort_values(["eom", "permno"])
    portfolio, deciles = portfolio_analytics(
        prediction_frame,
        transaction_cost=transaction_cost,
    )
    optimization_details = {"enabled": False, "method": "equal_weight"}
    if portfolio_optimization:
        if portfolio_mode != "long_short":
            raise ValueError("MAXSER-PR portfolio optimization requires Long-Short mode")
        import qlib
        provider = os.environ.get("WRDS_QLIB_DATA_DIR") or os.environ.get("QLIB_DATA_DIR")
        if not provider:
            raise ValueError("WRDS_QLIB_DATA_DIR is required for MAXSER-PR daily risk estimation")
        qlib.init(provider_uri=provider, region="us")
        from quantaalpha.backtest.portfolio_optimization import calculate_maxser_pr_analytics
        optimized_signal = prediction_frame.assign(
            instrument=prediction_frame["permno"].map(lambda value: f"P{int(value)}")
        ).set_index(["eom", "instrument"])["score"]
        optimized_signal.index = optimized_signal.index.set_names(["datetime", "instrument"])
        optimization_config = {
            "data": {"market": "sp500"},
            "backtest": {
                "backtest": {"start_time": test_start, "end_time": test_end},
                "long_short": {"transaction_cost": transaction_cost, "short_borrow_rate": 0.0},
            },
        }
        optimized, optimization_details = calculate_maxser_pr_analytics(optimized_signal, optimization_config)
        portfolio["long_short_equal_weight"] = portfolio["long_short"]
        portfolio["long_short"] = optimized
    ic = ic_metrics(prediction_frame)
    chosen = portfolio.get(portfolio_mode) or portfolio["long_short"]
    metrics = {
        **ic,
        "annualized_return": chosen.get("annualized_net_return", 0.0),
        "max_drawdown": chosen.get("max_drawdown", 0.0),
        "sharpe_ratio": chosen.get("sharpe_ratio", 0.0),
        "average_daily_turnover": chosen.get("average_daily_turnover", 0.0),
        "portfolio_analytics": portfolio,
        "portfolio_optimization": optimization_details,
        "decile_analytics": deciles,
        "cumulative_curve": chosen.get("curve", []),
        "prediction_frequency": "month",
        "expanding_window": True,
        "missing_threshold": missing_threshold,
        "retrain_months": retrain_months,
        "selected_factor_count_min": min(selected_counts),
        "selected_factor_count_max": max(selected_counts),
        "selected_factor_count_last": len(selected_last),
        "prediction_months": int(prediction_frame["eom"].nunique()),
        "model_type": model_type,
        "training_seconds": time.time() - training_started,
        "validation_detail": validation_detail,
        "missing_value_policy": "same_month_cross_sectional_median_after_rank; fully_missing_month=0",
        "correlation_pruning": correlation_report,
    }

    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    stem = f"kelly_jkp_expanding_{timestamp}"
    prediction_frame.to_parquet(output_dir / f"{stem}_predictions.parquet", index=False, compression="zstd")
    result = {
        "experiment_name": stem,
        "factor_source": "kelly_jkp",
        "num_factors": len(selected_last),
        "metrics": metrics,
        "config": {
            "data_range": f"{panel['eom'].min().date()} ~ {panel['eom'].max().date()}",
            "train_range": f"{train_start_ts.date()} ~ {train_end_ts.date()}",
            "valid_range": f"{valid_start_ts.date()} ~ {valid_end_ts.date()}",
            "test_range": f"{test_dates.min().date()} ~ {test_dates.max().date()}",
            "backtest_range": f"{test_dates.min().date()} ~ {test_dates.max().date()}",
            "market": "sp500",
            "benchmark": "ret_exc_lead1m",
            "missing_threshold": missing_threshold,
            "retrain_months": retrain_months,
            "min_train_years": min_train_years,
            "model_type": model_type,
            "validation_detail": validation_detail,
            "missing_value_policy": "same_month_cross_sectional_median_after_rank; fully_missing_month=0",
            "selected_factors_last": selected_last,
        },
        "elapsed_seconds": time.time() - started,
    }
    output = output_dir / f"{stem}_backtest_metrics.json"
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from quantaalpha.backtest.retention import enforce_backtest_retention
    retention = enforce_backtest_retention(
        output_dir,
        project_root=Path(__file__).resolve().parents[2],
        keep=int(os.environ.get("BACKTEST_RESULT_RETENTION", "3")),
    )
    metrics["storage_retention"] = retention
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[4/4] Kelly Expanding Window 回测完成，结果已保存: {output}", flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--missing-threshold", type=float, default=0.20)
    parser.add_argument("--model", choices=["lightgbm", "pls5", "lasso"], default="lightgbm")
    parser.add_argument("--retrain-months", type=int, default=12)
    parser.add_argument("--min-train-years", type=int, default=10)
    parser.add_argument("--train-start", default="1987-01-01")
    parser.add_argument("--train-end", default="2010-12-31")
    parser.add_argument("--valid-start", default="2011-01-01")
    parser.add_argument("--valid-end", default="2014-12-31")
    parser.add_argument("--test-start", default="2015-01-01")
    parser.add_argument("--test-end", default="2025-12-31")
    parser.add_argument("--portfolio-mode", choices=["long", "short", "long_short"], default="long_short")
    parser.add_argument("--transaction-cost", type=float, default=0.0005)
    parser.add_argument("--portfolio-optimization", action="store_true")
    parser.add_argument("--correlation-pruning", action="store_true")
    parser.add_argument("--correlation-threshold", type=float, default=0.85)
    args = parser.parse_args()
    run_expanding_backtest(
        panel_path=args.panel,
        output_dir=args.output_dir,
        missing_threshold=args.missing_threshold,
        model_type=args.model,
        retrain_months=args.retrain_months,
        min_train_years=args.min_train_years,
        train_start=args.train_start,
        train_end=args.train_end,
        valid_start=args.valid_start,
        valid_end=args.valid_end,
        test_start=args.test_start,
        test_end=args.test_end,
        portfolio_mode=args.portfolio_mode,
        transaction_cost=args.transaction_cost,
        portfolio_optimization=args.portfolio_optimization,
        correlation_pruning=args.correlation_pruning,
        correlation_threshold=args.correlation_threshold,
    )


if __name__ == "__main__":
    main()

"""Long/short portfolio analytics shared by mining and backtests."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd

VALID_FREQUENCIES = ("day", "week", "month")

def _series(data, name):
    s = data if isinstance(data, pd.Series) else data.iloc[:, 0]
    if not isinstance(s.index, pd.MultiIndex) or s.index.nlevels < 2:
        raise ValueError(f"{name} must use a datetime/instrument MultiIndex")
    names = list(s.index.names)
    di = names.index("datetime") if "datetime" in names else 0
    ii = names.index("instrument") if "instrument" in names else 1
    dt = pd.to_datetime(s.index.get_level_values(di), errors="coerce")
    if dt.isna().any():
        raise ValueError(f"{name} contains invalid datetimes")
    out = s.copy()
    out.index = pd.MultiIndex.from_arrays(
        [dt, s.index.get_level_values(ii).astype(str)], names=["datetime", "instrument"]
    )
    return out[~out.index.duplicated(keep="last")].sort_index()

def _rebalance_dates(dates, frequency):
    unique = pd.DatetimeIndex(dates.unique()).sort_values()
    if frequency == "day":
        return set(unique)
    period = unique.to_period("W-FRI" if frequency == "week" else "M")
    return set(pd.DataFrame({"date": unique, "period": period}).groupby("period", observed=True)["date"].max())

def _weights(group, quantile, minimum):
    group = group.sort_values("score")
    n = min(max(minimum, int(np.ceil(len(group) * quantile))), len(group) // 2)
    if n < 1:
        return {}
    low, high = group.iloc[:n], group.iloc[-n:]
    long = pd.Series(1.0 / n, index=high.index)
    short = pd.Series(-1.0 / n, index=low.index)
    result = {"long": long, "short": short, "long_short": pd.concat([long * .5, short * .5])}
    for i, members in enumerate(np.array_split(group.index.to_numpy(), 10), 1):
        if len(members):
            result[f"group_{i}"] = pd.Series(1.0 / len(members), index=members)
    return result

def _summary(rows, rebalances):
    if not rows:
        return {}
    frame = pd.DataFrame(rows).set_index("date").sort_index()
    net, gross = frame.net_return.clip(lower=-.999999), frame.gross_return.clip(lower=-.999999)
    ne, ge = (1 + net).cumprod(), (1 + gross).cumprod()
    periods, std = len(frame), float(net.std(ddof=1)) if len(frame) > 1 else 0.0
    annual = lambda e: float(e.iloc[-1] ** (252.0 / periods) - 1.0)
    dd = ne / ne.cummax() - 1
    active = frame.loc[frame.is_rebalance, "turnover"]
    return {
        "annualized_gross_return": annual(ge), "annualized_net_return": annual(ne),
        "total_net_return": float(ne.iloc[-1] - 1), "annualized_volatility": std * np.sqrt(252.0),
        "sharpe_ratio": float(net.mean() / std * np.sqrt(252.0)) if std > 0 else 0.0,
        "max_drawdown": float(dd.min()), "average_daily_turnover": float(frame.turnover.mean()),
        "average_turnover_per_rebalance": float(active.mean()) if len(active) else 0.0,
        "annualized_turnover": float(frame.turnover.mean() * 252.0),
        "total_transaction_cost": float(frame.transaction_cost.sum()),
        "total_borrow_cost": float(frame.borrow_cost.sum()),
        "average_positions": float(frame.positions.mean()), "rebalance_count": int(rebalances),
        "curve": [{"date": d.strftime("%Y-%m-%d"), "value": float(v - 1)} for d, v in ne.items()],
        "daily_net_returns": [
            {"date": d.strftime("%Y-%m-%d"), "value": float(v)}
            for d, v in net.items()
        ],
    }

def calculate_multi_frequency_analytics(signal, realized, frequencies=("day",), *,
        quantile=.1, min_positions=20, transaction_cost=.0005, short_borrow_rate=0.0):
    """Daily P&L for daily/weekly/monthly rebalancing; long-short is 50/50."""
    joined = pd.concat([_series(signal, "signal").rename("score"),
                        _series(realized, "return").rename("realized_return")], axis=1, join="inner")
    joined = joined.replace([np.inf, -np.inf], np.nan).dropna()
    if joined.empty:
        raise ValueError("No prediction/return overlap for long-short analytics")
    frequencies = list(dict.fromkeys(str(f).strip().lower() for f in frequencies)) or ["day"]
    bad = [f for f in frequencies if f not in VALID_FREQUENCIES]
    if bad:
        raise ValueError(f"Unsupported evaluation frequencies: {bad}")
    dates = pd.DatetimeIndex(joined.index.get_level_values("datetime").unique()).sort_values()
    names = ["long", "short", "long_short", *[f"group_{i}" for i in range(1, 11)]]
    output = {}
    for frequency in frequencies:
        rebalance_dates = _rebalance_dates(dates, frequency)
        previous = {n: pd.Series(dtype=float) for n in names}
        current = {n: pd.Series(dtype=float) for n in names}
        records = {n: [] for n in names}
        count = 0
        for date, raw in joined.groupby(level="datetime", sort=True):
            date, group = pd.Timestamp(date), raw.droplevel("datetime")
            is_rebalance = date in rebalance_dates
            if is_rebalance:
                target = _weights(group, quantile, min_positions)
                if target:
                    current.update(target); count += 1
            returns = group.realized_return
            for name in names:
                weight = current[name]
                if weight.empty:
                    continue
                turnover = float(weight.subtract(previous[name], fill_value=0).abs().sum()) if is_rebalance else 0.0
                gross = float((weight * returns.reindex(weight.index).fillna(0)).sum())
                cost = turnover * transaction_cost
                borrow = short_borrow_rate / 252.0 * float(weight[weight < 0].abs().sum())
                records[name].append({"date": date, "gross_return": gross,
                    "net_return": gross - cost - borrow, "turnover": turnover,
                    "transaction_cost": cost, "borrow_cost": borrow,
                    "positions": len(weight), "is_rebalance": is_rebalance})
                if is_rebalance:
                    previous[name] = weight.copy()
        portfolios = {n: _summary(records[n], count) for n in ("long", "short", "long_short") if records[n]}
        deciles = {n: _summary(records[n], count) for n in (f"group_{i}" for i in range(1, 11)) if records[n]}
        dr = pd.Series({int(n.split("_")[1]): v["annualized_net_return"] for n, v in deciles.items()})
        output[frequency] = {"portfolio_analytics": portfolios, "decile_analytics": deciles,
            "decile_monotonicity": float(dr.index.to_series().corr(dr, method="spearman")) if len(dr) > 1 else 0.0,
            "top_minus_bottom_annualized_return": float(dr.get(10, 0) - dr.get(1, 0))}
    return output


def calculate_ic_metrics(signal, realized):
    """Cross-sectional daily IC/RankIC means and information ratios."""
    joined = pd.concat([_series(signal, "signal").rename("score"),
                        _series(realized, "return").rename("realized_return")], axis=1, join="inner")
    joined = joined.replace([np.inf, -np.inf], np.nan).dropna()
    pearson, spearman = [], []
    for _, group in joined.groupby(level="datetime", sort=True):
        if len(group) < 3 or group.score.nunique() < 2 or group.realized_return.nunique() < 2:
            continue
        pearson.append(group.score.corr(group.realized_return, method="pearson"))
        spearman.append(group.score.corr(group.realized_return, method="spearman"))

    def summarize(values):
        series = pd.Series(values, dtype=float).dropna()
        if series.empty:
            return 0.0, 0.0
        mean = float(series.mean())
        std = float(series.std(ddof=1)) if len(series) > 1 else 0.0
        return mean, mean / std if std > 0 else 0.0

    ic, icir = summarize(pearson)
    rank_ic, rank_icir = summarize(spearman)
    return {"IC": ic, "ICIR": icir, "Rank IC": rank_ic, "Rank ICIR": rank_icir}

def flatten_analytics(analytics):
    flat = {}
    fields = ("annualized_gross_return", "annualized_net_return", "sharpe_ratio", "max_drawdown",
              "average_turnover_per_rebalance", "annualized_turnover",
              "total_transaction_cost", "total_borrow_cost", "rebalance_count")
    for frequency, payload in analytics.items():
        for portfolio, summary in payload.get("portfolio_analytics", {}).items():
            for field in fields:
                if field in summary:
                    flat[f"{frequency}.{portfolio}.{field}"] = float(summary[field])
        flat[f"{frequency}.decile_monotonicity"] = float(payload.get("decile_monotonicity", 0))
        flat[f"{frequency}.decile_top_minus_bottom_annualized_return"] = float(payload.get("top_minus_bottom_annualized_return", 0))
        for name, summary in payload.get("decile_analytics", {}).items():
            flat[f"{frequency}.{name}.annualized_net_return"] = float(summary["annualized_net_return"])
    return flat



GICS_LEVELS = ("gsector", "ggroup", "gind", "gsubind")


def _classification_levels(classifications, levels=None):
    if levels:
        return tuple(levels)
    if classifications is None:
        return GICS_LEVELS
    detected = tuple(str(column) for column in classifications.columns)
    return detected or GICS_LEVELS


def _normalize_classifications(classifications, levels=None):
    if classifications is None:
        return None
    levels = _classification_levels(classifications, levels)
    columns = [level for level in levels if level in classifications.columns]
    if not columns:
        return pd.DataFrame()
    return pd.concat(
        [_series(classifications[level], level).rename(level) for level in columns],
        axis=1,
    )


def industry_rank_signal(signal, classifications, level="gsector", levels=None):
    """Rank a signal within each date/industry bucket and center it around zero."""
    allowed = _classification_levels(classifications, levels)
    if level not in allowed:
        raise ValueError(f"Unsupported industry level: {level}")
    score = _series(signal, "signal").rename("signal")
    classifications = _normalize_classifications(classifications, allowed)
    if classifications is None or level not in classifications.columns:
        return pd.Series(dtype=float, name=f"{level}_rank")
    joined = pd.concat([score, classifications[[level]]], axis=1, join="inner")
    joined = joined.replace([np.inf, -np.inf], np.nan).dropna()
    if joined.empty:
        return pd.Series(dtype=float, name=f"{level}_rank")
    dates = joined.index.get_level_values("datetime")
    groups = [dates, joined[level]]
    ranked = joined.groupby(groups, observed=True)["signal"].rank(method="average")
    centered = ranked - ranked.groupby(groups, observed=True).transform("mean")
    scale = centered.abs().groupby(groups, observed=True).transform("max").replace(0, np.nan)
    ranked = (centered / scale).fillna(0.0)
    ranked.name = f"{level}_rank"
    return ranked.sort_index()


def calculate_industry_diagnostics(signal, classifications, levels=None):
    """Measure coverage and cross-sectional exposure at every configured level."""
    score = _series(signal, "signal").rename("signal")
    levels = _classification_levels(classifications, levels)
    classifications = _normalize_classifications(classifications, levels)
    output = {}
    for level in levels:
        if classifications is None or level not in classifications.columns:
            continue
        joined = pd.concat([score, classifications[[level]]], axis=1, join="inner")
        finite_score = joined["signal"].replace([np.inf, -np.inf], np.nan)
        valid = finite_score.notna()
        covered = valid & joined[level].notna()
        output[f"industry.{level}.coverage"] = float(covered.sum() / max(valid.sum(), 1))
        frame = joined.loc[covered, ["signal", level]].copy()
        if frame.empty:
            continue
        dates = frame.index.get_level_values("datetime")
        means = frame.groupby(dates)["signal"].transform("mean")
        stds = frame.groupby(dates)["signal"].transform("std").replace(0, np.nan)
        frame["zscore"] = (frame["signal"] - means) / stds
        group_exposure = frame.groupby([dates, frame[level]], observed=True)["zscore"].mean().dropna()
        if group_exposure.empty:
            continue
        output[f"industry.{level}.mean_abs_exposure"] = float(group_exposure.abs().mean())
        output[f"industry.{level}.max_abs_exposure"] = float(group_exposure.abs().max())
        abs_exp = group_exposure.abs()
        shares = abs_exp / abs_exp.groupby(level=0).transform("sum").replace(0, np.nan)
        hhi = shares.pow(2).groupby(level=0).sum().dropna()
        output[f"industry.{level}.exposure_hhi"] = float(hhi.mean()) if len(hhi) else 0.0
        output[f"industry.{level}.group_count"] = float(frame[level].nunique())
    return output


def calculate_industry_aware_analytics(
    signal, realized, classifications, frequencies=("day",), *,
    classification_levels=None, primary_level=None, robustness_level=None, **kwargs
):
    """Evaluate a factor using the selected market's industry hierarchy."""
    levels = _classification_levels(classifications, classification_levels)
    primary_level = primary_level or ("gsector" if "gsector" in levels else levels[0])
    robustness_level = robustness_level or (
        "ggroup" if "ggroup" in levels else (levels[1] if len(levels) > 1 else primary_level)
    )
    primary_signal = industry_rank_signal(signal, classifications, primary_level, levels)
    if primary_signal.empty:
        # Missing classifications must not discard an otherwise valid factor.
        # Evaluate the raw signal and mark the result explicitly as a fallback;
        # callers and the LLM can distinguish it from industry-neutral results.
        raw_signal = _series(signal, "signal").replace([np.inf, -np.inf], np.nan).dropna()
        raw = calculate_multi_frequency_analytics(
            raw_signal, realized, frequencies=frequencies, **kwargs
        )
        metrics = flatten_analytics(raw)
        metrics.update(calculate_ic_metrics(raw_signal, realized))
        metrics.update({f"industry.raw.{key}": value for key, value in calculate_ic_metrics(raw_signal, realized).items()})
        metrics.update(calculate_industry_diagnostics(raw_signal, classifications, levels))
        metrics["industry.neutralization_available"] = 0.0
        metrics[f"industry.primary_level_{primary_level}"] = 0.0
        metrics[f"industry.robustness_level_{robustness_level}"] = 0.0
        return raw_signal, raw, {}, metrics
    primary = calculate_multi_frequency_analytics(
        primary_signal, realized, frequencies=frequencies, **kwargs
    )
    metrics = flatten_analytics(primary)
    metrics.update(calculate_ic_metrics(primary_signal, realized))
    raw_ic = calculate_ic_metrics(signal, realized)
    metrics.update({f"industry.raw.{key}": value for key, value in raw_ic.items()})
    metrics.update(calculate_industry_diagnostics(signal, classifications, levels))
    metrics["industry.neutralization_available"] = 1.0

    robust_signal = industry_rank_signal(signal, classifications, robustness_level, levels)
    robust_analytics = {}
    if not robust_signal.empty:
        robust_analytics = calculate_multi_frequency_analytics(
            robust_signal, realized, frequencies=frequencies, **kwargs
        )
        robust_metrics = flatten_analytics(robust_analytics)
        robust_metrics.update(calculate_ic_metrics(robust_signal, realized))
        metrics.update({f"industry.{robustness_level}.robustness.{key}": value for key, value in robust_metrics.items()})

    metrics[f"industry.primary_level_{primary_level}"] = 1.0
    metrics[f"industry.robustness_level_{robustness_level}"] = 1.0
    return primary_signal, primary, robust_analytics, metrics

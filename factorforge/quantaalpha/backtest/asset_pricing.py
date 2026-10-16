"""Asset-pricing regressions against WRDS Fama-French factors."""
from __future__ import annotations
import io
import zipfile
from pathlib import Path
from typing import Iterable
import numpy as np
import pandas as pd
from scipy import stats

SPECS = {
    "ff3": ["mktrf", "smb", "hml"],
    "ff3_mom": ["mktrf", "smb", "hml", "umd"],
    "ff5": ["mktrf", "smb", "hml", "rmw", "cma"],
    "ff5_mom": ["mktrf", "smb", "hml", "rmw", "cma", "umd"],
}

def _csv_from_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        member = next(info for info in archive.infolist() if not info.is_dir())
        with archive.open(member) as stream:
            return pd.read_csv(stream)

def load_wrds_factors(wrds_root: str | Path) -> pd.DataFrame:
    root = Path(wrds_root)
    folder = root / "CRSP" / "FamaFactor"
    ff3 = _csv_from_zip(folder / "Fama-French 3 Factors Plus Momentum - Daily Frequency.zip")
    ff5 = _csv_from_zip(folder / "5 Factors Plus Momentum - Daily Frequency.zip")
    for frame in (ff3, ff5):
        frame.columns = [str(column).strip().lower() for column in frame.columns]
        frame["date"] = pd.to_datetime(frame["date"])
    factors = ff5.set_index("date").combine_first(ff3.set_index("date"))
    for column in factors.columns:
        factors[column] = pd.to_numeric(factors[column], errors="coerce")
    return factors.sort_index()

def _newey_west_covariance(x: np.ndarray, residual: np.ndarray, lag: int) -> np.ndarray:
    n, _ = x.shape
    bread = np.linalg.pinv(x.T @ x)
    scores = x * residual[:, None]
    meat = scores.T @ scores
    for distance in range(1, min(lag, n - 1) + 1):
        weight = 1.0 - distance / (lag + 1.0)
        gamma = scores[distance:].T @ scores[:-distance]
        meat += weight * (gamma + gamma.T)
    return bread @ meat @ bread

def regress_with_factor_frame(
    portfolio_returns: pd.Series | Iterable[dict],
    factors: pd.DataFrame,
    hac_lags: int = 5,
) -> dict[str, dict[str, float]]:
    """Run the common FF3/FF5/Mom regression set against an explicit factor frame."""
    if isinstance(portfolio_returns, pd.Series):
        returns = portfolio_returns.copy()
        returns.index = pd.to_datetime(returns.index)
    else:
        frame = pd.DataFrame(list(portfolio_returns))
        returns = pd.Series(
            pd.to_numeric(frame["value"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["date"]),
            name="portfolio_return",
        )
    returns = returns.groupby(level=0).last().sort_index().rename("portfolio_return")
    factors = factors.copy()
    factors.index = pd.to_datetime(factors.index)
    factors.columns = [str(column).strip().lower() for column in factors.columns]
    joined = pd.concat([returns, factors,], axis=1, join="inner")
    results: dict[str, dict[str, float]] = {}
    for name, columns in SPECS.items():
        sample = joined[["portfolio_return", *columns]].replace([np.inf, -np.inf], np.nan).dropna()
        n = len(sample)
        k = len(columns) + 1
        if n <= k + 2:
            continue
        y = sample["portfolio_return"].to_numpy(dtype=float)
        x = np.column_stack([np.ones(n), sample[columns].to_numpy(dtype=float)])
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        residual = y - x @ beta
        cov = _newey_west_covariance(x, residual, hac_lags)
        se = np.sqrt(np.maximum(np.diag(cov), 0.0))
        t_values = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
        dof = max(n - k, 1)
        p_values = 2.0 * stats.t.sf(np.abs(t_values), dof)
        tss = float(((y - y.mean()) ** 2).sum())
        rss = float((residual ** 2).sum())
        r2 = 1.0 - rss / tss if tss > 0 else 0.0
        adj_r2 = 1.0 - (1.0 - r2) * (n - 1.0) / max(n - k, 1)
        values = {
            "alpha_daily": float(beta[0]),
            "alpha_annualized": float(beta[0] * 252.0),
            "alpha_t_stat": float(t_values[0]),
            "alpha_p_value": float(p_values[0]),
            "r_squared": float(r2),
            "adjusted_r_squared": float(adj_r2),
            "residual_volatility_annualized": float(np.std(residual, ddof=k) * np.sqrt(252.0)),
            "observations": float(n),
            "hac_lags": float(hac_lags),
        }
        for idx, factor in enumerate(columns, 1):
            values[f"beta_{factor}"] = float(beta[idx])
            values[f"beta_{factor}_t_stat"] = float(t_values[idx])
            values[f"beta_{factor}_p_value"] = float(p_values[idx])
        results[name] = values
    return results

def regress_asset_pricing(
    portfolio_returns: pd.Series | Iterable[dict],
    wrds_root: str | Path,
    hac_lags: int = 5,
) -> dict[str, dict[str, float]]:
    return regress_with_factor_frame(portfolio_returns, load_wrds_factors(wrds_root), hac_lags=hac_lags)


def flatten_asset_pricing(results: dict[str, dict[str, float]], prefix: str = "asset_pricing") -> dict[str, float]:
    return {
        f"{prefix}.{model}.{metric}": float(value)
        for model, metrics in results.items()
        for metric, value in metrics.items()
    }

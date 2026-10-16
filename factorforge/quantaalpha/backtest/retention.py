"""Bound disk growth from disposable backtest artifacts."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def _remove(path: Path) -> int:
    try:
        if not path.exists():
            return 0
        size = path.stat().st_size if path.is_file() else sum(
            item.stat().st_size for item in path.rglob("*") if item.is_file()
        )
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return size
    except OSError as exc:
        logger.warning("Unable to remove stale backtest artifact %s: %s", path, exc)
        return 0


def enforce_backtest_retention(
    output_dir: str | Path,
    *,
    project_root: str | Path,
    keep: int = 3,
) -> dict:
    """Keep the newest completed result sets and MLflow signal runs.

    Factor-value caches are deliberately excluded because they are reused by
    later backtests and are expensive to rebuild.
    """
    output = Path(output_dir).resolve()
    removed_files = removed_runs = reclaimed = 0

    groups: dict[str, list[Path]] = {"standard": [], "kelly_jkp": []}
    for path in output.glob("*_backtest_metrics.json"):
        group = "kelly_jkp" if path.name.startswith("kelly_jkp_") else "standard"
        groups[group].append(path)
    for metrics_files in groups.values():
        metrics_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for metrics in metrics_files[max(1, keep):]:
            stem = metrics.name[:-len("_backtest_metrics.json")]
            companions = [
                metrics,
                output / f"{stem}_predictions.parquet",
                output / f"{stem}_cumulative_excess.csv",
            ]
            for path in companions:
                if path.exists():
                    reclaimed += _remove(path)
                    removed_files += 1

    mlruns = Path(project_root).resolve() / "mlruns"
    signal_runs = []
    if mlruns.exists():
        for pred in mlruns.glob("*/*/artifacts/pred.pkl"):
            run_dir = pred.parent.parent
            signal_runs.append(run_dir)
    signal_runs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for run_dir in signal_runs[max(1, keep):]:
        reclaimed += _remove(run_dir)
        removed_runs += 1

    report = {
        "keep": max(1, keep),
        "removed_result_files": removed_files,
        "removed_mlflow_runs": removed_runs,
        "reclaimed_bytes": reclaimed,
    }
    if reclaimed:
        logger.info("Backtest retention reclaimed %.1f MB: %s", reclaimed / 1024**2, report)
    return report

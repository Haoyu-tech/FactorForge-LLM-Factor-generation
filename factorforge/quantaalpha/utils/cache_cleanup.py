"""Safe cleanup of disposable QuantaAlpha mining artifacts."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Iterable


_MD5_FILE = re.compile(r"^[0-9a-f]{32}\.pkl$", re.IGNORECASE)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file() and not child.is_symlink():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def _old_enough(path: Path, hours: float, now: float) -> bool:
    try:
        return now - path.stat().st_mtime >= max(hours, 0.0) * 3600
    except OSError:
        return False


def _remove(path: Path, *, allowed_root: Path, dry_run: bool) -> int:
    if not _inside(path, allowed_root) or path.resolve() == allowed_root.resolve():
        return 0
    amount = _size(path)
    if dry_run:
        return amount
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=False)
    else:
        path.unlink(missing_ok=True)
    return amount


def _referenced_factor_cache_keys(factorlib_dir: Path) -> set[str]:
    """Return signals needed by the newest library for each market universe.

    Historical library JSON files already contain their saved charts and
    statistics. Keeping a full daily stock-by-factor signal for every old
    snapshot made disk use grow by roughly one large file per mined factor.
    If an old factor later needs a new split or heatmap, its signal can be
    reconstructed from the stored expression on demand.
    """
    keys: set[str] = set()
    newest: dict[tuple[str, str], tuple[float, dict]] = {}
    for library in factorlib_dir.glob("all_factors_library*.json"):
        try:
            payload = json.loads(library.read_text(encoding="utf-8"))
        except Exception:
            continue
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        filename = library.name.lower()
        market_mode = str(metadata.get("market_mode") or (
            "cn" if "all_factors_library_cn_" in filename else "us"
        )).lower()
        market = str(metadata.get("market") or "").lower()
        if not market:
            if market_mode == "cn":
                market = next((name for name in ("csi300", "csi500", "sme_composite")
                               if f"all_factors_library_cn_{name}" in filename), "csi300")
            else:
                market = "sp500"
        scope = (market_mode, market)
        modified = library.stat().st_mtime
        if scope not in newest or modified > newest[scope][0]:
            newest[scope] = (modified, payload)

    for _, payload in newest.values():
        for factor in (payload.get("factors", {}) or {}).values():
            expression = str(factor.get("factor_expression", "")).strip()
            if expression:
                keys.add(hashlib.md5(expression.encode()).hexdigest())
    return keys


def cleanup_mining_artifacts(
    project_root: str | Path,
    *,
    finished_workspace: str | Path | None = None,
    finished_pickle_cache: str | Path | None = None,
    finished_log_root: str | Path | None = None,
    stale_hours: float = 24.0,
    log_cache_hours: float = 6.0,
    orphan_factor_cache_hours: float = 24.0,
    dry_run: bool = False,
) -> dict:
    """Remove disposable caches without touching datasets or published results."""
    project = Path(project_root).resolve()
    data_root = project / "data"
    log_root = project / "log"
    now = time.time()
    removed: list[dict] = []

    def remove(path: Path, category: str, allowed_root: Path):
        if not path.exists():
            return
        amount = _remove(path, allowed_root=allowed_root, dry_run=dry_run)
        if amount or not path.exists():
            removed.append({"category": category, "path": str(path), "bytes": amount})

    # The just-finished job is safe to delete immediately: factors needed by
    # the library have already been copied into the stable MD5 factor cache.
    for raw, prefix in (
        (finished_workspace, "workspace_exp_"),
        (finished_pickle_cache, "pickle_cache_exp_"),
    ):
        if not raw:
            continue
        path = Path(raw).resolve()
        if path.name.startswith(prefix) and _inside(path, data_root):
            remove(path, "finished_task", data_root)

    # Sweep abandoned per-experiment workspaces and pickle caches under any
    # configured results root inside project/data.
    for pattern in ("workspace_exp_*", "pickle_cache_exp_*"):
        for path in data_root.glob(f"**/{pattern}"):
            if _old_enough(path, stale_hours, now):
                remove(path, "stale_task", data_root)

    # Immediately clear parallel-worker caches from the just-finished run,
    # while retaining its readable logs, state and trajectory summaries.
    if finished_log_root:
        finished_log = Path(finished_log_root).resolve()
        if _inside(finished_log, log_root):
            for path in finished_log.glob("pickle_cache_*"):
                remove(path, "finished_log_pickle_cache", log_root)

    # Parallel workers place large pickle caches inside dated log folders.
    # Delete only those cache directories; keep readable logs and trajectories.
    if log_root.exists():
        for path in log_root.glob("*/pickle_cache_*"):
            if _old_enough(path, log_cache_hours, now):
                remove(path, "log_pickle_cache", log_root)

    # Keep full signals for each market's newest library. Historical JSONs keep
    # their compact charts/statistics; a missing old signal is rebuilt lazily.
    factor_cache = project / "data" / "results" / "factor_cache"
    referenced = _referenced_factor_cache_keys(project / "data" / "factorlib")
    if factor_cache.exists():
        for path in factor_cache.glob("*.pkl"):
            if (_MD5_FILE.match(path.name) and path.stem not in referenced
                    and _old_enough(path, orphan_factor_cache_hours, now)):
                remove(path, "orphan_factor_cache", factor_cache)

    total = sum(item["bytes"] for item in removed)
    return {
        "dry_run": dry_run,
        "removed_count": len(removed),
        "bytes_freed": total,
        "gigabytes_freed": round(total / (1024 ** 3), 3),
        "items": removed,
    }

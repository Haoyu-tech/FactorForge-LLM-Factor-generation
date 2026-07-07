# -*- coding: utf-8 -*-
"""Run manifest writer for reproducible experiment folders."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT, get_config, path


def run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}"


def _git_commit() -> str | None:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def file_fingerprint(p: str | Path) -> dict[str, Any]:
    fp = Path(p)
    out: dict[str, Any] = {"path": str(fp)}
    if not fp.exists():
        out["exists"] = False
        return out
    out.update({"exists": True, "size_bytes": fp.stat().st_size})
    h = hashlib.sha256()
    with fp.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    out["sha256"] = h.hexdigest()
    return out


def write_manifest(
    outdir: str | Path,
    *,
    run_name: str,
    params: dict[str, Any] | None = None,
    inputs: dict[str, str | Path] | None = None,
    notes: str | None = None,
) -> Path:
    out = Path(outdir)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    cfg = get_config()
    manifest = {
        "schema_version": 1,
        "run_name": run_name,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "git_commit": _git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "config": cfg,
        "params": params or {},
        "inputs": {k: file_fingerprint(v) for k, v in (inputs or {}).items()},
        "notes": notes or "",
    }
    p = out / "MANIFEST.json"
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def default_input_paths() -> dict[str, Path]:
    names = ["panel", "membership_panel", "pv_panel", "legacy_panel"]
    return {name: path(name) for name in names}

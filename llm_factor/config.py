# -*- coding: utf-8 -*-
"""Single source of truth for paths and experiment defaults.

The adapter scripts started as stand-alone research scripts. This module keeps
them compatible while moving all machine-specific state into config files and
environment overrides.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "llm_factor.json"


@lru_cache(maxsize=4)
def get_config(config_path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG
    if not cfg_path.is_absolute():
        cfg_path = PROJECT_ROOT / cfg_path
    with cfg_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    return p if p.is_absolute() else PROJECT_ROOT / p


def path(name: str, config_path: str | Path | None = None, must_exist: bool = False) -> Path:
    cfg = get_config(config_path)
    try:
        spec = cfg["paths"][name]
    except KeyError as exc:
        raise KeyError(f"unknown configured path: {name}") from exc
    raw = os.environ.get(spec.get("env", ""), spec["default"])
    p = _resolve(raw)
    if must_exist and not p.exists():
        env_hint = f" Set {spec['env']} or edit {DEFAULT_CONFIG}." if spec.get("env") else ""
        raise FileNotFoundError(f"configured path '{name}' does not exist: {p}.{env_hint}")
    return p


def sample(name: str, default: Any = None) -> Any:
    return get_config().get("sample", {}).get(name, default)


def evaluation(name: str, default: Any = None) -> Any:
    return get_config().get("evaluation", {}).get(name, default)


def search(name: str, default: Any = None) -> Any:
    return get_config().get("search", {}).get(name, default)

# -*- coding: utf-8 -*-
"""Factor registry helpers.

Curated factors live in configs/factors.json so all experiments consume the same
declared set rather than copying DEFAULT_FACTORS across scripts.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT

DEFAULT_REGISTRY = PROJECT_ROOT / "configs" / "factors.json"


@lru_cache(maxsize=4)
def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_REGISTRY
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def factor_records(set_name: str = "thesis_core") -> list[dict[str, Any]]:
    records = load_registry()["sets"][set_name]
    return [dict(r) for r in records]


def factor_tuples(set_name: str = "thesis_core") -> dict[str, tuple[str, str]]:
    return {r["name"]: (r["expression"], r.get("rationale", "")) for r in factor_records(set_name)}


def factor_exprs(set_name: str = "thesis_core") -> dict[str, str]:
    return {r["name"]: r["expression"] for r in factor_records(set_name)}

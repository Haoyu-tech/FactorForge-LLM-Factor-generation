# -*- coding: utf-8 -*-
"""Append-only candidate ledger for LLM/search-generated factors."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import path


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class CandidateLedger:
    """JSONL ledger. One candidate per line, including failures."""

    def __init__(self, run_id: str, root: str | Path | None = None):
        base = Path(root) if root else path("candidate_ledger_root")
        self.path = base / f"{run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, **record: Any) -> None:
        record.setdefault("created_at_utc", now_utc())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

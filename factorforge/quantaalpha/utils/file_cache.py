"""Memoise a computation over a file until the file changes.

Factor libraries are JSON files of up to tens of megabytes. Parsing them on
every API request blocked the backend for seconds at a time, so readers cache
what they derive from a file, keyed by its modification time and size.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Hashable, Iterable, Tuple


class FileStatCache:
    """Values derived from files, rebuilt when a file's mtime or size changes.

    `build` receives the resolved path. A build that raises is not cached.
    Builds run under one lock, so concurrent requests for the same file parse
    it once instead of once each.
    """

    def __init__(self) -> None:
        self._entries: Dict[Tuple[str, Hashable], Tuple[Tuple[int, int], Any]] = {}
        self._lock = threading.Lock()

    def get(self, path: str | Path, build: Callable[[str], Any], extra: Hashable = ()) -> Any:
        resolved = str(Path(path).resolve())
        # Stat before reading: a write that lands mid-build leaves the old
        # stamp on the entry, so the next call rebuilds.
        stat = os.stat(resolved)
        stamp = (stat.st_mtime_ns, stat.st_size)
        key = (resolved, extra)
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None and hit[0] == stamp:
                return hit[1]
            value = build(resolved)
            self._entries[key] = (stamp, value)
            return value

    def retain(self, paths: Iterable[str | Path]) -> None:
        """Forget files that are not in `paths`, e.g. deleted libraries."""
        keep = {str(Path(path).resolve()) for path in paths}
        with self._lock:
            for key in [key for key in self._entries if key[0] not in keep]:
                del self._entries[key]

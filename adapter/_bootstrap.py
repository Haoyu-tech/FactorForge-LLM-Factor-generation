# -*- coding: utf-8 -*-
"""Compatibility bootstrap for running adapter scripts by file path."""
from pathlib import Path
import sys


def ensure_project_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    adapter = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if str(adapter) not in sys.path:
        sys.path.insert(0, str(adapter))
    return root


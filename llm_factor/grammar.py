# -*- coding: utf-8 -*-
"""Configured operator grammars shared by LLM prompts and GP generation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import get_config, search


@dataclass(frozen=True)
class OperatorGrammar:
    name: str
    spec: dict[str, Any]

    @property
    def cross_sectional_unary(self) -> list[str]:
        return list(self.spec.get("cross_sectional_unary", []))

    @property
    def time_series_unary(self) -> list[str]:
        return list(self.spec.get("time_series_unary", []))

    @property
    def math_unary(self) -> list[str]:
        return list(self.spec.get("math_unary", []))

    @property
    def binary(self) -> list[str]:
        return list(self.spec.get("binary", []))

    @property
    def windows(self) -> list[int]:
        return list(self.spec.get("windows", []))

    @property
    def max_terms(self) -> int:
        return int(self.spec.get("max_terms", 3))

    @property
    def top_wrapper(self) -> str:
        return str(self.spec.get("top_wrapper", "RANK"))

    def leaf_fields(self, available_fields: list[str]) -> list[str]:
        raw = self.spec.get("leaf_fields", "all")
        if raw == "all":
            return list(available_fields)
        avail = set(available_fields)
        return [f for f in raw if f in avail]

    def operator_prompt(self) -> str:
        parts = []
        if self.binary:
            parts.append("Arithmetic: " + " ".join(self.binary))
        if self.math_unary:
            parts.append("Math unary: " + " ".join(self.math_unary))
        if self.cross_sectional_unary:
            parts.append("Cross-sectional(per month): " + " ".join(self.cross_sectional_unary))
        if self.time_series_unary:
            ts = " ".join(f"{op}(x,p)" for op in self.time_series_unary)
            parts.append(f"Time-series(per stock, p in {self.windows}, window=months): {ts}")
        if self.spec.get("time_series_binary"):
            parts.append("Time-series binary: " + " ".join(self.spec["time_series_binary"]))
        if self.spec.get("math_binary"):
            parts.append("Math binary: " + " ".join(self.spec["math_binary"]))
        if self.spec.get("conditional"):
            parts.append("Conditional/comparison: " + " ".join(self.spec["conditional"]))
        return " | ".join(parts)


def get_grammar(name: str | None = None) -> OperatorGrammar:
    cfg = get_config()
    grammar_name = name or search("primary_grammar", "fast_full")
    try:
        spec = cfg["operator_grammars"][grammar_name]
    except KeyError as exc:
        raise KeyError(f"unknown operator grammar: {grammar_name}") from exc
    return OperatorGrammar(grammar_name, spec)

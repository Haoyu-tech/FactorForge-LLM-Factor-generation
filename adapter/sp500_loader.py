# -*- coding: utf-8 -*-
"""
SP500 monthly loader + factor compute - the bridge that lets QuantaAlpha's
expression engine run on our WRDS monthly multi-factor panel instead of qlib.

What it provides
----------------
load_features()  -> DataFrame  MultiIndex (datetime, instrument), $-cols only
                    == drop-in replacement for QuantaAlpha get_qlib_stock_data()
load_labels()    -> Series     next-month excess return (the IC target)
compute_factor(expr) -> Series factor values for an AlphaAgent-style expression

Why we re-wrap the compute step (instead of calling CustomFactorCalculator):
QuantaAlpha substitutes $columns with a naive str.replace(col[1:], ...), which
corrupts overlapping names (e.g. '$me' inside '$be_me', '$at' inside
'$at_turnover'). Our characteristic columns overlap heavily, so we do a
word-boundary, single-pass substitution instead. The PARSER (parse_symbol /
parse_expression) and the OPERATOR LIBRARY (function_lib) are reused unchanged.
"""
import importlib.util
import io
import os
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from llm_factor.config import path

ROOT = Path(__file__).resolve().parents[1]
# Default: full official-universe panel (~500/month) = price/volume + curated
# multi-category Kelly-153 characteristics. Override via SP500_PANEL env:
#   sp500_monthly_pv.parquet     -> price/volume only (full universe, 1928+)
#   sp500_monthly.parquet        -> 36-col characteristics sample
PANEL = path("panel")
CODER = ROOT / "QuantaAlpha" / "quantaalpha" / "factors" / "coder"


# ---------------------------------------------------------------- coder import
def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# loaded standalone so the heavy coder/__init__ (CoSTEER, qlib...) is bypassed
_func_lib = _load_module("qa_function_lib", CODER / "function_lib.py")
_parser = _load_module("qa_expr_parser", CODER / "expr_parser.py")

# operator namespace exposed to eval (RANK, TS_MEAN, ADD, ...)
_FUNCS = {
    n: getattr(_func_lib, n)
    for n in dir(_func_lib)
    if not n.startswith("_") and callable(getattr(_func_lib, n))
}


# ---------------------------------------------------------------- data loading
_panel_cache = None


def _panel() -> pd.DataFrame:
    global _panel_cache
    if _panel_cache is None:
        df = pd.read_parquet(PANEL)
        if df.index.duplicated().any():
            df = df[~df.index.duplicated(keep="last")]
        numeric_cols = [c for c in df.columns if c.startswith("$") or c == "label"]
        for c in numeric_cols:
            if not pd.api.types.is_numeric_dtype(df[c]):
                df[c] = pd.to_numeric(df[c], errors="coerce")
        _panel_cache = df
    return _panel_cache


def load_features(start=None, end=None) -> pd.DataFrame:
    """$-prefixed feature panel (no label). Drop-in for get_qlib_stock_data()."""
    df = _panel()
    feats = [c for c in df.columns if c.startswith("$")]
    out = df[feats]
    if start or end:
        dt = out.index.get_level_values("datetime")
        mask = np.ones(len(out), dtype=bool)
        if start:
            mask &= dt >= pd.Timestamp(start)
        if end:
            mask &= dt <= pd.Timestamp(end)
        out = out[mask]
    return out.copy()


def load_labels(start=None, end=None) -> pd.Series:
    df = _panel()
    s = df["label"]
    if start or end:
        dt = s.index.get_level_values("datetime")
        mask = np.ones(len(s), dtype=bool)
        if start:
            mask &= dt >= pd.Timestamp(start)
        if end:
            mask &= dt <= pd.Timestamp(end)
        s = s[mask]
    return s.copy()


def available_fields() -> list:
    return [c for c in _panel().columns if c.startswith("$")]


# ---------------------------------------------------------------- compute
def _to_python(expr: str, columns) -> str:
    """AlphaAgent expression -> evaluable python string referencing df['$col']."""
    # 1) strip $ via QuantaAlpha's symbol map (safe: keys carry the $ prefix)
    stripped = _parser.parse_symbol(expr, columns)
    # 2) build function-call form (suppress the parser's debug print)
    with redirect_stdout(io.StringIO()):
        pyexpr = _parser.parse_expression(stripped)
    # 3) word-boundary, single-pass substitution of bare names -> df["$name"]
    names = sorted((c[1:] for c in columns), key=len, reverse=True)
    pat = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b")
    pyexpr = pat.sub(lambda m: f'df["${m.group(1)}"]', pyexpr)
    return pyexpr


def compute_factor(expr: str, data_df: pd.DataFrame = None) -> pd.Series:
    """Evaluate an AlphaAgent-style factor expression on the monthly panel."""
    df = (load_features() if data_df is None else data_df).copy()
    if "$return" in df.columns and "$close" in df.columns:
        pass  # already provided
    pyexpr = _to_python(expr, df.columns)
    g = {"df": df, "np": np, "pd": pd, **_FUNCS}
    result = eval(pyexpr, {"__builtins__": {}}, g)
    if isinstance(result, pd.DataFrame):
        result = result.iloc[:, 0]
    if not isinstance(result, pd.Series):
        result = pd.Series(result, index=df.index)
    result = result.reindex(df.index)
    result.name = expr
    return result.astype(np.float64)


if __name__ == "__main__":
    print(f"panel rows : {len(_panel()):,}")
    print(f"fields     : {available_fields()}")
    test = sys.argv[1] if len(sys.argv) > 1 else "RANK($gp_at) - RANK($be_me)"
    print(f"\nexpr       : {test}")
    print("python     :", _to_python(test, available_fields()))
    f = compute_factor(test)
    print(f"non-NaN    : {f.notna().sum():,}/{len(f):,}")
    print(f.dropna().head())


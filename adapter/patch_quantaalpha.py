# -*- coding: utf-8 -*-
"""
Monkeypatch QuantaAlpha to read our monthly S&P 500 panel instead of qlib.
Import this ONCE before launching the mining loop:

    import patch_quantaalpha   # noqa: F401  (applies the patches on import)

Requires QuantaAlpha's own deps to be installed (so `quantaalpha.*` imports
resolve). It does NOT require qlib data - that's the whole point.
"""
import sys
from pathlib import Path

import pandas as pd

ADAPTER = Path(__file__).resolve().parent
ROOT = ADAPTER.parent
for p in (str(ADAPTER), str(ROOT / "QuantaAlpha")):
    if p not in sys.path:
        sys.path.insert(0, p)

from sp500_loader import load_features, load_labels  # noqa: E402


def _our_stock_data(config=None) -> pd.DataFrame:
    """Drop-in for get_qlib_stock_data(): returns our monthly $-feature panel."""
    data_cfg = (config or {}).get("data", {}) if isinstance(config, dict) else {}
    return load_features(start=data_cfg.get("start_time"), end=data_cfg.get("end_time"))


def apply():
    # 1) data source used by the custom-factor calculator
    import quantaalpha.backtest.custom_factor_calculator as cfc
    cfc.get_qlib_stock_data = _our_stock_data

    # 2) label: use the precomputed next-month excess return instead of a
    #    daily close-to-close expression. We expose it as LABEL0 keyed by index.
    orig_to_qlib = cfc.CustomFactorDataLoader.to_qlib_format

    def _monthly_to_qlib(self, data_df):
        labels = load_labels().reindex(data_df.index)
        return self.factor_df, pd.DataFrame({"LABEL0": labels})

    cfc.CustomFactorDataLoader.to_qlib_format = _monthly_to_qlib

    print("[patch_quantaalpha] data loader + monthly label patched "
          f"({len(_our_stock_data())} rows from sp500_monthly.parquet)")


apply()


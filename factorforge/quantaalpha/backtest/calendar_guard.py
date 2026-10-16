"""Keep one Qlib trading day after a portfolio backtest end date."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional


def clamp_backtest_end_date(
    config: Dict[str, Any], provider_uri: Optional[str] = None
) -> Optional[str]:
    """Clamp only the tradable portfolio window; data/test windows stay intact."""
    if 'port_analysis_config' in config:
        backtest = (config.get('port_analysis_config') or {}).get('backtest') or {}
        qlib_init = config.get('qlib_init') or {}
        configured_provider = qlib_init.get('provider_uri')
    else:
        backtest = ((config.get('backtest') or {}).get('backtest') or {})
        configured_provider = (config.get('data') or {}).get('provider_uri')

    requested_end = str(backtest.get('end_time') or '')
    provider = provider_uri or os.environ.get('QLIB_DATA_DIR') or configured_provider
    if not requested_end or not provider:
        return None

    calendar_path = Path(os.path.expanduser(str(provider))) / 'calendars' / 'day.txt'
    if not calendar_path.exists():
        return None
    trading_days = [line.strip() for line in calendar_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(trading_days) < 2:
        return None

    latest_safe_end = trading_days[-2]
    if requested_end > latest_safe_end:
        backtest['end_time'] = latest_safe_end
        return latest_safe_end
    return None

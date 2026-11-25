"""Split guards: calendar look-ahead at the sample end and between splits.

* ``clamp_backtest_end_date`` keeps one Qlib trading day after a portfolio
  backtest end date.
* ``enforce_valid_test_gap`` leaves full trading sessions between the last
  validation label and the first test date.
* ``mining_evaluation_split`` refuses to let mining score on the test window.
"""

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


# The daily label Ref($close,-2)/Ref($close,-1)-1 (or Ref($ret_total,-2)) at
# date t is realised at the close of t+2. Two full sessions between the last
# validation date and the first test date mean every validation label is
# known before the first test signal is formed.
VALID_TEST_GAP_SESSIONS = 2


def enforce_valid_test_gap(segments: Dict[str, Any], calendar, gap_sessions: int = VALID_TEST_GAP_SESSIONS) -> Optional[str]:
    """Move the validation end back so ``gap_sessions`` sessions precede the test start.

    ``calendar`` is the sorted list of trading days. Returns the new
    validation end date when it was moved, otherwise None. The test window is
    never shortened.
    """
    import pandas as pd

    valid, test = segments.get('valid'), segments.get('test')
    if not (isinstance(valid, (list, tuple)) and len(valid) == 2 and isinstance(test, (list, tuple)) and test):
        return None
    days = pd.DatetimeIndex(pd.to_datetime(list(calendar))).sort_values()
    test_start = pd.Timestamp(test[0])
    position = int(days.searchsorted(test_start, side='left'))  # first session >= test start
    latest = position - 1 - int(gap_sessions)
    if latest < 0:
        return None
    latest_valid = days[latest]
    if pd.Timestamp(valid[1]) <= latest_valid:
        return None
    if latest_valid < pd.Timestamp(valid[0]):
        raise ValueError(
            f"Validation window {valid[0]} to {valid[1]} is too short to leave "
            f"{gap_sessions} sessions before the test start {test[0]}"
        )
    new_end = latest_valid.strftime('%Y-%m-%d')
    segments['valid'] = [valid[0], new_end]
    return new_end


def mining_evaluation_split(environment: Optional[Dict[str, str]] = None) -> str:
    """Return the split mining feedback may use; only validation is allowed.

    Scoring candidates on the test window would select factors on the same
    data used to report them, so ``MINING_EVALUATION_SPLIT=test`` is refused
    rather than honoured.
    """
    env = os.environ if environment is None else environment
    split = str(env.get('MINING_EVALUATION_SPLIT', 'valid') or 'valid').strip().lower()
    if split == 'test':
        raise ValueError(
            'MINING_EVALUATION_SPLIT=test is blocked: mining must not see the test '
            'window. Use the frozen split evaluation for test results.'
        )
    return 'valid'

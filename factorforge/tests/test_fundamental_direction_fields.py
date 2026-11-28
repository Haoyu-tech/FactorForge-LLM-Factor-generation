"""Fields that satisfy the fundamental-direction check must cover every exported non-price field."""
from quantaalpha.data.ibes_adapter import IBES_FIELDS
from quantaalpha.factors.proposal import active_fundamental_fields, uses_fundamental_field


def test_us_fields_include_reporting_timing_and_ibes():
    fields = active_fundamental_fields("us")
    for name in ("$atq", "$roa_q", "$report_lag_days", "$fundamental_age_days"):
        assert name in fields
    for name in IBES_FIELDS:
        assert f"${name}" in fields
    # Industry codes classify firms; on their own they are not a fundamental signal.
    assert "$gsector" not in fields


def test_late_reporter_factor_is_not_flagged_price_only():
    expr = "-($report_lag_days - DELAY($report_lag_days, 252))"
    assert uses_fundamental_field(expr, active_fundamental_fields("us"))


def test_price_only_factor_is_still_flagged():
    expr = "TS_MEAN(-1*TS_CORR($open/DELAY($close,1)-1,$close/$open-1,63),5)"
    assert not uses_fundamental_field(expr, active_fundamental_fields("us"))


def test_crypto_fields_unchanged():
    assert "$funding_rate" in active_fundamental_fields("crypto")
    assert "$atq" not in active_fundamental_fields("crypto")

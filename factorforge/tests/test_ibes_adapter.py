"""IBES fields: CUSIP link to PERMNO, next-session timing, staleness, and scaling."""
from __future__ import annotations

from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from quantaalpha.data import ibes_adapter as ib


def _ts(value):
    return pd.Timestamp(value)


def test_links_follow_the_cusip_spells_of_a_ticker():
    idsum = pd.DataFrame({
        "ticker": ["ABC", "ABC", "ABC", "XYZ"],
        "cusip": ["11111110", "11111110", "22222220", "33333330"],
        "sdates": ["2000-01-20", "2003-01-16", "2005-06-16", "2001-01-18"],
    })
    crsp = pd.DataFrame({
        "cusip": ["11111110", "22222220", "33333330"],
        "permno": [10001, 10002, 10003],
        "crsp_start": [_ts("1995-01-01"), _ts("2005-06-01"), _ts("2002-01-01")],
        "crsp_end": [_ts("2005-06-30"), _ts("2020-12-31"), _ts("2010-12-31")],
    })
    links = ib.build_links(idsum, crsp).set_index("permno")
    # First spell starts at the CRSP range, not the first IBES snapshot.
    assert links.loc[10001, "start"] == _ts("1995-01-01")
    # It ends the day before the ticker's next CUSIP appears.
    assert links.loc[10001, "end"] == _ts("2005-06-15")
    assert links.loc[10002, "start"] == _ts("2005-06-16") and links.loc[10002, "end"] == _ts("2020-12-31")
    # A later spell cannot start before CRSP knows the CUSIP.
    assert links.loc[10003, "start"] == _ts("2002-01-01")

    rows = pd.DataFrame({"ticker": ["ABC", "ABC", "ABC"],
                         "event_date": [_ts("2004-01-15"), _ts("2006-01-19"), _ts("2021-01-21")],
                         "value": [1, 2, 3]})
    linked = ib.link_rows(rows, links.reset_index(), "event_date")
    assert linked[["permno", "value"]].values.tolist() == [[10001, 1], [10002, 2]]


def _daily(dates, raw_close):
    return pd.DataFrame({"date": pd.to_datetime(dates), "raw_close": raw_close})


SESSIONS = ["2024-01-17", "2024-01-18", "2024-01-19", "2024-01-22", "2024-03-01", "2024-03-05"]


def test_consensus_is_usable_from_the_next_session_and_expires():
    rec = pd.DataFrame({
        "event_date": [_ts("2024-01-18")], "ibes_rec_mean": [2.0], "ibes_rec_count": [8.0],
        "ibes_rec_net_up": [float(Fraction(3 - 1, 8))], "ibes_rec_buy_pct": [0.5],
        "ibes_rec_sell_pct": [0.125], "ibes_rec_dispersion": [0.75],
    })
    out = ib.attach_ibes(_daily(SESSIONS, [100.0] * 6), {"rec": rec}).set_index("date")
    # Not on the statistics date itself.
    assert np.isnan(out.loc["2024-01-18", "ibes_rec_mean"])
    assert out.loc["2024-01-19", "ibes_rec_mean"] == 2.0
    assert out.loc["2024-01-22", "ibes_rec_net_up"] == 0.25
    # 2024-03-01 is 43 days later: still current. 2024-03-05 is 47 days: dropped.
    assert out.loc["2024-03-01", "ibes_rec_mean"] == 2.0
    assert np.isnan(out.loc["2024-03-05", "ibes_rec_mean"])
    assert set(ib.IBES_FIELDS) <= set(out.columns)


def test_price_target_upside_uses_the_unadjusted_price_on_the_consensus_date():
    ptg = pd.DataFrame({
        "event_date": [_ts("2024-01-18")], "meanptg": [120.0], "ibes_ptg_count": [10.0],
        "ibes_ptg_net_revision": [0.3], "ibes_ptg_dispersion": [float(Fraction(6, 120))],
    })
    # Price on 2024-01-18 is 100; later prices must not change the upside.
    out = ib.attach_ibes(_daily(SESSIONS, [90.0, 100.0, 150.0, 150.0, 150.0, 150.0]), {"ptg": ptg}).set_index("date")
    assert out.loc["2024-01-19", "ibes_ptg_upside"] == pytest.approx(float(Fraction(120, 100) - 1), abs=1e-12)
    assert out.loc["2024-01-22", "ibes_ptg_dispersion"] == pytest.approx(0.05, abs=1e-12)


def test_surprise_is_scaled_by_the_close_before_the_announcement():
    surprise = pd.DataFrame({"event_date": [_ts("2024-01-18")], "ibes_sue": [2.5], "eps_gap": [0.10]})
    out = ib.attach_ibes(_daily(SESSIONS, [50.0, 80.0, 80.0, 80.0, 80.0, 80.0]), {"surprise": surprise}).set_index("date")
    assert np.isnan(out.loc["2024-01-18", "ibes_sue"])
    assert out.loc["2024-01-19", "ibes_sue"] == 2.5
    # 0.10 / 50 (close on 2024-01-17), not / 80 (the announcement-day close).
    assert out.loc["2024-01-19", "ibes_eps_surprise"] == pytest.approx(float(Fraction(1, 10) / 50), abs=1e-15)
    assert out.loc["2024-01-19", "ibes_surprise_age_days"] == 1
    assert out.loc["2024-03-05", "ibes_surprise_age_days"] == 47  # within the 120-day window


def test_no_ibes_rows_leaves_nan_columns():
    out = ib.attach_ibes(_daily(SESSIONS, [1.0] * 6), None)
    assert out[ib.IBES_FIELDS].isna().all().all()


def test_inspect_reports_missing_and_truncated_tables(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    for name in ("idsum", "recdsum", "ptgsumu"):
        pq.write_table(pa.table({"ticker": ["A"]}), tmp_path / f"{name}.parquet")
    (tmp_path / "ptgdetu.parquet").write_bytes(b"PAR1 truncated")
    status = ib.inspect_ibes(tmp_path)
    assert status["ready"] is False and status["missing"] == ["surpsumu"]
    assert status["unreadable"] == ["ptgdetu"]
    assert status["epsRevisionsAvailable"] is False
    assert ib.default_ibes_root(None, None) is None
    assert ib.default_ibes_root(tmp_path, str(tmp_path / "x")) == tmp_path / "x"


def test_microsecond_event_dates_merge_with_nanosecond_sessions():
    rec = pd.DataFrame({"event_date": pd.to_datetime(["2024-01-18"]).astype("datetime64[us]"),
                        **{field: [1.0] for field in ib.REC_FIELDS}})
    out = ib.attach_ibes(_daily(SESSIONS, [100.0] * 6), {"rec": rec}).set_index("date")
    assert out.loc["2024-01-19", "ibes_rec_mean"] == 1.0

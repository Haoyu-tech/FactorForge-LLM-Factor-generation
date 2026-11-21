"""Look-ahead and cost-accounting fixes in the portfolio analytics and data builders."""
import io
import zipfile
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from quantaalpha.backtest import long_short_analytics as lsa
from quantaalpha.backtest import portfolio_optimization as po
from quantaalpha.backtest.calendar_guard import enforce_valid_test_gap, mining_evaluation_split
from quantaalpha.backtest.kelly_expanding import portfolio_analytics as kelly_portfolio_analytics


def _panel(values, name):
    rows = [(pd.Timestamp(d), inst, v) for d, by_inst in values.items() for inst, v in by_inst.items()]
    index = pd.MultiIndex.from_tuples([(d, i) for d, i, _ in rows], names=["datetime", "instrument"])
    return pd.Series([v for _, _, v in rows], index=index, name=name, dtype=float)


def _long(result, frequency="day"):
    return result[frequency]["portfolio_analytics"]["long"]


# --- (b) formation must not depend on the future return ----------------------

def test_name_with_missing_next_return_is_not_dropped_at_formation():
    day = "2024-01-05"
    signal = _panel({day: {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}}, "score")
    # A (top score) is suspended / delisted: its next return does not exist.
    realized = _panel({day: {"B": 0.02, "C": 0.0, "D": 0.0}}, "ret")
    result = lsa.calculate_multi_frequency_analytics(
        signal, realized, ("day",), quantile=0.5, min_positions=1, periods_per_year=252)
    long = _long(result)
    # Long book is {A, B} at 1/2 each; A is booked at 0, so the day earns 1%.
    # Dropping A before formation would have picked {B, C} and earned 1% too,
    # so check the composition and the reported missing exposure directly.
    assert long["average_positions"] == 2
    assert long["daily_net_returns"][0]["value"] == pytest.approx(0.01 - 1.0 * 0.0005)
    assert long["missing_return_exposure"] == pytest.approx(0.5)


def test_held_name_keeps_earning_after_its_signal_drops_out():
    signal = _panel({
        "2024-01-05": {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0},
        "2024-01-08": {"B": 3.0, "C": 2.0, "D": 1.0},  # A lost its signal (e.g. left the index)
        "2024-01-12": {"B": 3.0, "C": 2.0, "D": 1.0},  # next weekly rebalance
    }, "score")
    realized = _panel({
        "2024-01-05": {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
        "2024-01-08": {"A": 0.10, "B": 0.0, "C": 0.0, "D": 0.0},
        "2024-01-12": {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
    }, "ret")
    result = lsa.calculate_multi_frequency_analytics(
        signal, realized, ("week",), quantile=0.5, min_positions=1,
        transaction_cost=0.0, periods_per_year=252)
    daily = [row["value"] for row in _long(result, "week")["daily_net_returns"]]
    # The book formed on Friday still holds A on Monday: half of A's 10%.
    assert daily == pytest.approx([0.0, 0.05, 0.0])


def test_sessions_without_any_realized_return_are_not_pnl_days():
    signal = _panel({"2024-01-05": {"A": 2.0, "B": 1.0}, "2024-01-08": {"A": 2.0, "B": 1.0}}, "score")
    realized = _panel({"2024-01-05": {"A": 0.01, "B": 0.0}}, "ret")  # last label not realised yet
    result = lsa.calculate_multi_frequency_analytics(
        signal, realized, ("day",), quantile=0.5, min_positions=1, periods_per_year=252)
    assert [row["date"] for row in _long(result)["daily_net_returns"]] == ["2024-01-05"]


# --- (c) weights drift between rebalances ------------------------------------

def test_turnover_is_measured_from_drifted_weights():
    names = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}
    signal = _panel({d: names for d in ("2024-01-05", "2024-01-08", "2024-01-12")}, "score")
    realized = _panel({
        "2024-01-05": {"A": 0.10, "B": -0.05, "C": 0.0, "D": 0.0},
        "2024-01-08": {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
        "2024-01-12": {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
    }, "ret")
    result = lsa.calculate_multi_frequency_analytics(
        signal, realized, ("week",), quantile=0.5, min_positions=1,
        transaction_cost=0.0, periods_per_year=252)
    long = _long(result, "week")
    # After +10% / -5% on a 1/2-1/2 book: w_A = (1/2)(11/10)/(41/40) = 22/41.
    w_a = Fraction(1, 2) * Fraction(11, 10) / (1 + Fraction(1, 2) * Fraction(1, 10) - Fraction(1, 2) * Fraction(1, 20))
    assert w_a == Fraction(22, 41)
    expected_rebalance = 2 * (w_a - Fraction(1, 2))  # back to 1/2-1/2 on Jan 12
    assert expected_rebalance == Fraction(3, 41)
    # Turnover per rebalance: the first trade (1.0) and the drift correction (3/41).
    assert long["average_turnover_per_rebalance"] == pytest.approx(float((1 + Fraction(3, 41)) / 2))


def test_drift_weights_formula():
    weights = pd.Series({"L": 0.5, "S": -0.5})
    returns = pd.Series({"L": 0.04, "S": 0.02})
    gross = float((weights * returns).sum())  # 0.01
    drifted = lsa.drift_weights(weights, returns, gross)
    assert drifted["L"] == pytest.approx(float(Fraction(1, 2) * Fraction(104, 100) / Fraction(101, 100)))
    assert drifted["S"] == pytest.approx(float(Fraction(-1, 2) * Fraction(102, 100) / Fraction(101, 100)))


def test_kelly_monthly_keeps_missing_returns_and_charges_drift():
    rows = []
    for eom, returns in (("2020-01-31", (0.10, -0.05, 0.0, 0.0)), ("2020-02-29", (0.0, 0.0, 0.0, 0.0))):
        for permno, (score, ret) in enumerate(zip((4.0, 3.0, 2.0, 1.0), returns), start=1):
            rows.append({"eom": pd.Timestamp(eom), "permno": permno, "score": score, "ret_exc_lead1m": ret})
    frame = pd.DataFrame(rows)
    frame.loc[(frame.eom == "2020-02-29") & (frame.permno == 1), "ret_exc_lead1m"] = np.nan
    portfolios, _ = kelly_portfolio_analytics(frame, quantile=0.5, min_positions=1, transaction_cost=0.0)
    long = portfolios["long"]
    assert long["average_positions"] == 2  # permno 1 stays despite the missing return
    assert long["average_turnover_per_rebalance"] == pytest.approx(float((1 + Fraction(3, 41)) / 2))
    assert long["missing_return_exposure"] == pytest.approx(0.25)


# --- (d) MAXSER-PR alignment and units ---------------------------------------

def test_label_execution_lag():
    assert po.label_execution_lag("Ref($ret_total, -1)") == 0
    assert po.label_execution_lag("Ref($ret_total, -2)") == 1
    assert po.label_execution_lag("Ref($close, -2) / Ref($close, -1) - 1") == 1
    assert po.label_execution_lag(None) == 0


def test_calendar_month_end_signals_cover_every_session():
    sessions = pd.bdate_range("2010-01-01", "2012-12-31")
    month_ends = pd.date_range("2010-01-31", "2012-11-30", freq="M")  # calendar month-ends
    assert (~month_ends.isin(sessions)).sum() > 0  # some fall on weekends
    signal = _panel({d: {"A": 1.0, "B": -1.0} for d in month_ends}, "score")
    # Old alignment: reindex calendar dates onto sessions, then forward-fill.
    old = signal.unstack("instrument").reindex(sessions).ffill()
    snapped = po.snap_to_sessions(signal, sessions).unstack("instrument").reindex(sessions)
    new = po.signal_in_force(snapped, lag=0)
    held = sessions[(sessions > month_ends[0]) & (sessions <= month_ends[-1])]
    assert new.loc[held].notna().all().all()
    # Old alignment leaves sessions at the start with no signal at all.
    assert old.loc[held].isna().any(axis=1).sum() > 0
    # A Sunday month-end lands on the Friday before it.
    assert po.snap_to_sessions(_panel({"2010-01-31": {"A": 1.0}}, "s"), sessions).index[0][0] == pd.Timestamp("2010-01-29")


def test_signal_in_force_uses_the_snapshot_before_the_trade():
    sessions = pd.bdate_range("2024-01-01", periods=5)
    scores = pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=sessions)
    # Return on session t is forecast by the score from t-1-lag.
    assert po.signal_in_force(scores, lag=0)["A"].tolist()[1:] == [1.0, 2.0, 3.0, 4.0]
    assert po.signal_in_force(scores, lag=1)["A"].tolist()[2:] == [1.0, 2.0, 3.0]


def test_signal_slope_puts_scores_in_daily_return_units():
    rng = np.random.default_rng(0)
    ranks = rng.uniform(-1, 1, size=(120, 60))  # rank-like scores
    returns = 0.002 * ranks + 0.01  # a market move common to all names
    slope, days = po.signal_return_slope(returns, ranks)
    assert days == 120
    assert slope == pytest.approx(0.002)


# --- (f) split guards ----------------------------------------------------------

def test_valid_end_moves_back_two_sessions_before_test():
    calendar = pd.to_datetime(["2009-12-28", "2009-12-29", "2009-12-30", "2009-12-31", "2010-01-04", "2010-01-05"])
    segments = {"valid": ["2000-01-03", "2009-12-31"], "test": ["2010-01-04", "2025-12-31"]}
    assert enforce_valid_test_gap(segments, calendar) == "2009-12-29"
    assert segments["valid"] == ["2000-01-03", "2009-12-29"]
    assert segments["test"] == ["2010-01-04", "2025-12-31"]
    assert enforce_valid_test_gap(segments, calendar) is None  # already gapped


def test_valid_window_too_short_for_the_gap_raises():
    calendar = pd.to_datetime(["2009-12-29", "2009-12-30", "2009-12-31", "2010-01-04"])
    with pytest.raises(ValueError):
        enforce_valid_test_gap({"valid": ["2009-12-31", "2009-12-31"], "test": ["2010-01-04", "2010-12-31"]}, calendar)


def test_mining_cannot_evaluate_on_test():
    assert mining_evaluation_split({}) == "valid"
    assert mining_evaluation_split({"MINING_EVALUATION_SPLIT": "valid"}) == "valid"
    with pytest.raises(ValueError, match="blocked"):
        mining_evaluation_split({"MINING_EVALUATION_SPLIT": "test"})
    with pytest.raises(ValueError):
        mining_evaluation_split({"MINING_EVALUATION_SPLIT": " TEST "})


# --- (e) point-in-time universes ---------------------------------------------

def test_crypto_universe_ranks_on_prior_volume_and_keeps_delisted():
    from quantaalpha.data.binance_futures_adapter import point_in_time_membership

    days = pd.date_range("2021-01-01", periods=60, freq="D")
    big = pd.DataFrame({"date": days, "quote_volume": 100.0})
    small = pd.DataFrame({"date": days, "quote_volume": 10.0})
    small.loc[40:, "quote_volume"] = 1000.0  # surge from day 40
    dead = pd.DataFrame({"date": days[:30], "quote_volume": 500.0})  # delisted after day 29
    spans = point_in_time_membership({"BIG": big, "SMALL": small, "DEAD": dead},
                                     max_symbols=1, lookback_days=5, min_days=5)
    by_symbol = {}
    for symbol, start, end in spans:
        by_symbol.setdefault(symbol, []).append((start, end))
    # DEAD leads while it trades (from day 5, once it has 5 prior days), then exits.
    assert by_symbol["DEAD"] == [("2021-01-06", "2021-01-30")]
    # SMALL's surge on day 40 only counts from day 41 on; it overtakes BIG
    # once its 5-day trailing mean passes 100 (day 41: (4*10+1000)/5 = 208).
    assert by_symbol["SMALL"] == [("2021-02-11", "2021-03-01")]
    assert by_symbol["BIG"] == [("2021-01-31", "2021-02-10")]


def test_candidate_contracts_include_delisted(monkeypatch):
    from quantaalpha.data import binance_futures_adapter as bfa

    def fake_json(path, params=None, retries=5):
        assert path == "/fapi/v1/exchangeInfo"
        return {"symbols": [
            {"symbol": "BTCUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "TRADING"},
            {"symbol": "OLDUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "SETTLING"},
            {"symbol": "BTCUSDT_250328", "contractType": "CURRENT_QUARTER", "quoteAsset": "USDT", "status": "TRADING"},
        ]}

    prefix = "data/futures/um/monthly/klines/"
    monkeypatch.setattr(bfa, "_json_get", fake_json)
    monkeypatch.setattr(bfa, "_archive_list", lambda p, delimiter=None: [
        f"{prefix}BTCUSDT/", f"{prefix}GONEUSDT/", f"{prefix}ETHUSDT_240329/", f"{prefix}ETHBUSD/"])
    contracts, report = bfa._candidate_contracts(include_delisted=True)
    symbols = {item["symbol"]: item["status"] for item in contracts}
    assert symbols == {"BTCUSDT": "TRADING", "OLDUSDT": "SETTLING", "GONEUSDT": "DELISTED"}
    assert report["archiveOnly"] == 1 and report["exchangeNotTrading"] == 1


def _zip_csv(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("data.csv", text)
    return buffer.getvalue()


@pytest.mark.parametrize("header", [True, False])
def test_archive_csv_with_or_without_header(monkeypatch, header):
    from quantaalpha.data import binance_futures_adapter as bfa

    row = "1609459200000,1,2,0.5,1.5,10,1609545599999,15,3,4,6,0"
    text = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,"
            "taker_buy_volume,taker_buy_quote_volume,ignore\n" if header else "") + row + "\n"
    monkeypatch.setattr(bfa, "_get_bytes", lambda url, retries=5: _zip_csv(text))
    frame = bfa._read_archive_csv("data/futures/um/monthly/klines/X/1d/X-1d-2021-01.zip")
    assert frame.shape == (1, 12) and frame.iat[0, 0] == "1609459200000"


def test_crypto_contracts_are_not_held_to_the_a_share_new_stock_rule():
    from quantaalpha.market.profile import apply_market_eligibility

    index = pd.MultiIndex.from_tuples([(pd.Timestamp("2024-01-02"), "NEWUSDT")], names=["datetime", "instrument"])
    signal = pd.Series([1.0], index=index)
    frame = pd.DataFrame({"listing_age_days": [120.0], "is_st": [1.0]}, index=index)  # > 90, < 375
    kept = apply_market_eligibility(signal, frame, {"MARKET_MODE": "crypto"})
    assert kept.notna().all()
    # The same frame in China mode is cut by both A-share rules.
    assert apply_market_eligibility(signal, frame, {"MARKET_MODE": "cn"}).isna().all()


def test_china_listing_dates_cover_delisted_codes(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    from quantaalpha.data.cn_duckdb_adapter import _listing_dates

    path = tmp_path / "cn.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create table ts_stock_basic (ts_code varchar, list_date varchar, market varchar)")
    con.execute("insert into ts_stock_basic values ('600000.SH', '19991110', 'main')")
    con.execute("create table ts_daily (ts_code varchar, trade_date varchar)")
    con.execute("insert into ts_daily values ('600000.SH', '20100104'), ('600001.SH', '20100105'), "
                "('600001.SH', '20100106'), ('000300.SH', '20100104')")
    con.close()
    con = duckdb.connect(str(path), read_only=True)
    listing = _listing_dates(con).set_index("ts_code")
    assert listing.loc["600000.SH", "list_date"] == "19991110" and not listing.loc["600000.SH", "from_daily"]
    assert listing.loc["600001.SH", "list_date"] == "20100105" and listing.loc["600001.SH", "from_daily"]
    # The registered view used by the universe reconstruction works read-only.
    con.register("listing_dates", listing.reset_index()[["ts_code", "list_date"]])
    assert con.execute("select count(*) from listing_dates").fetchone()[0] == 3
    con.close()

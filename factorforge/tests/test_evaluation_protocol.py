"""The protocol text shown to the LLM must follow the evaluation settings."""
from quantaalpha.market.profile import describe_evaluation_protocol


def test_us_defaults_describe_the_single_factor_test():
    text = describe_evaluation_protocol({"MARKET_MODE": "us"})
    assert "validation period only" in text
    assert "day t+1 to day t+2" in text
    assert "gsector industry group" in text
    assert "top and bottom 10%" in text
    assert "rebalanced daily;" in text
    assert "5 bps" in text
    assert "top-minus-bottom" in text


def test_settings_change_the_text():
    text = describe_evaluation_protocol({
        "MARKET_MODE": "us",
        "MINING_EVALUATION_FREQUENCIES": "week, month",
        "LONG_SHORT_QUANTILE": "0.2",
        "LONG_SHORT_TRANSACTION_COST": "0.001",
    })
    assert "rebalanced weekly and monthly;" in text
    assert "top and bottom 20%" in text
    assert "10 bps" in text


def test_china_is_long_only_and_shenwan_ranked():
    text = describe_evaluation_protocol({"MARKET_MODE": "cn", "QLIB_MARKET": "csi500"})
    assert "sw_l1 industry group" in text
    assert "long-only top group" in text


def test_crypto_is_ranked_across_the_market():
    text = describe_evaluation_protocol({"MARKET_MODE": "crypto"})
    assert "ranked across the whole market" in text
    assert "industry group" not in text


def test_unparseable_settings_fall_back_to_defaults():
    text = describe_evaluation_protocol({
        "MARKET_MODE": "us",
        "MINING_EVALUATION_FREQUENCIES": "hourly",
        "LONG_SHORT_QUANTILE": "abc",
    })
    assert "rebalanced daily;" in text
    assert "top and bottom 10%" in text

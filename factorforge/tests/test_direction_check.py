"""The pre-mining direction check answers from the stored fields and the source registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from quantaalpha.research import data_feasibility as df
from quantaalpha.research.source_registry import (
    ALL_MARKETS,
    CATEGORIES_BY_ID,
    DATA_CATEGORIES,
    category_for_market,
)


def _store(tmp_path: Path, fields_by_instrument: dict[str, list[str]]) -> Path:
    for instrument, fields in fields_by_instrument.items():
        folder = tmp_path / "features" / instrument
        folder.mkdir(parents=True)
        for field in fields:
            (folder / f"{field}.day.bin").write_bytes(b"\0" * 8)
    return tmp_path


US_FIELDS = ["close", "volume", "open", "high", "low", "ret_total", "ceqq", "gross_profitability_q", "gsector"]


def test_store_fields_is_the_union_over_instruments(tmp_path):
    store = _store(tmp_path, {"a": ["close", "volume"], "b": ["close", "ceqq"], "c": []})
    (tmp_path / "features" / "a" / "notes.txt").write_text("not a field")
    assert df.store_fields(store) == ["ceqq", "close", "volume"]
    assert df.store_fields(tmp_path / "missing") == []
    assert df.store_fields(None) == []


def test_keyword_hits_match_whole_words_and_chinese():
    assert df.keyword_hits("Analyst forecast revisions after earnings") == ["analyst_forecasts", "analyst_eps_revisions"]
    assert df.keyword_hits("price target upside") == ["analyst_forecasts"]
    # "optional" must not read as options data, nor "decades" as CDS.
    assert df.keyword_hits("an optional liquidity filter over decades") == []
    assert "options" in df.keyword_hits("implied volatility skew of options")
    assert "short_interest" in df.keyword_hits("融资融券余额变化")
    assert "crypto_onchain" in df.keyword_hits("whale exchange inflow")


def test_category_status_uses_the_stored_fields():
    assert df.category_status("market_equity", "us", US_FIELDS) == "missing"
    assert df.category_status("market_equity", "cn", ["close", "total_mv"]) == "available"
    assert df.category_status("crypto_onchain", "us", US_FIELDS) == "wrong_market"


def test_invented_fields_do_not_count_as_data():
    llm = {
        "verdict": "feasible",
        "reply": "ok",
        "concepts": [
            {"concept": "short-term reversal", "status": "available", "fields": ["$close", "$ret_total"]},
            {"concept": "market capitalization", "status": "available", "fields": ["$market_cap"]},
        ],
        "suggested_direction": "",
    }
    result = df.assemble("reversal among small caps", "us", US_FIELDS, llm)
    reversal, size = result["concepts"][:2]
    assert reversal["status"] == "available" and reversal["fields"] == ["close", "ret_total"]
    assert size["status"] == "missing" and size["fields"] == []
    assert size["inventedFields"] == ["market_cap"]
    assert result["verdict"] == "partial"


def test_missing_data_gets_registry_sources_not_llm_text():
    llm = {
        "verdict": "unavailable",
        "reply": "Needs analyst data.",
        "concepts": [{
            "concept": "analyst forecast revisions", "status": "missing", "fields": [],
            "category_ids": ["analyst_forecasts", "not_a_category"],
            "search_terms": ["IBES revisions"],
        }],
        "suggested_direction": "",
    }
    result = df.assemble("Analyst forecast revisions", "us", US_FIELDS, llm)
    assert result["verdict"] == "unavailable"
    assert result["runDirection"] is None
    concept = result["concepts"][0]
    assert [c["id"] for c in concept["categories"]] == ["analyst_forecasts"]
    names = [s["name"] for s in concept["categories"][0]["sources"]]
    assert any("I/B/E/S" in name for name in names)
    # China-only sources are not offered for a US run.
    assert not any("Tushare" in name for name in names)
    assert all(p["url"].startswith("https://doi.org/10.") for p in concept["categories"][0]["papers"])
    assert result["replication"]["sources"]


def test_unlisted_keyword_hit_is_still_reported():
    llm = {"verdict": "feasible", "reply": "fine",
           "concepts": [{"concept": "momentum", "status": "available", "fields": ["$close"]}]}
    result = df.assemble("Momentum confirmed by option implied volatility", "us", US_FIELDS, llm)
    statuses = {c["concept"]: c["status"] for c in result["concepts"]}
    assert statuses["momentum"] == "available"
    assert statuses[CATEGORIES_BY_ID["options"]["label"]] == "missing"
    assert result["verdict"] == "partial"


def test_keyword_only_fallback_never_rules_a_direction_out():
    result = df.assemble("Small-cap value with high gross profitability", "us", US_FIELDS, None, "timeout")
    assert result["verdict"] == "partial"
    assert result["llm"] == {"used": False, "error": "timeout"}
    assert "did not answer" in result["reply"]


def test_run_direction_carries_the_check_into_mining():
    llm = {"verdict": "partial", "reply": "",
           "concepts": [
               {"concept": "reversal", "status": "available", "fields": ["close"]},
               {"concept": "analyst revisions", "status": "missing", "category_ids": ["analyst_forecasts"]},
           ]}
    result = df.assemble("Reversal after analyst revisions", "us", US_FIELDS, llm)
    text = result["runDirection"]
    assert text.startswith("Reversal after analyst revisions\n\n[Data check]")
    assert "$close" in text and "do not approximate" in text and "analyst revisions" in text
    plain = df.assemble("plain", "us", US_FIELDS, {"concepts": []})
    assert plain["verdict"] == "unclear" and plain["runDirection"] == "plain"


def test_check_direction_without_a_store_says_so(tmp_path):
    result = df.check_direction("anything", "cn", str(tmp_path), use_llm=False)
    assert result["verdict"] == "no_data" and result["runDirection"] is None


def test_check_direction_survives_a_failing_llm(tmp_path, monkeypatch):
    store = _store(tmp_path, {"a": US_FIELDS})

    class Broken:
        def build_messages_and_create_chat_completion(self, **_):
            raise RuntimeError("no channel")

    import quantaalpha.llm.client as client
    monkeypatch.setattr(client, "APIBackend", Broken)
    result = df.check_direction("insider purchases", "us", str(store))
    assert result["llm"]["used"] is False and "no channel" in result["llm"]["error"]
    assert [c["status"] for c in result["concepts"]] == ["missing"]


def test_prompt_lists_only_stored_fields():
    prompt = df.build_prompt("idea", "crypto", ["close", "funding_rate"], ["crypto_onchain"])
    assert "$funding_rate: daily sum of perpetual funding rates" in prompt
    assert "$ceqq" not in prompt
    assert "gsector" not in prompt
    assert "esg: ESG ratings and carbon emissions (not for this market)" in prompt


def test_registry_entries_are_complete():
    ids = [entry["id"] for entry in DATA_CATEGORIES]
    assert len(ids) == len(set(ids))
    for entry in DATA_CATEGORIES:
        assert set(entry["markets"]) <= set(ALL_MARKETS)
        assert entry["keywords"] and entry["satisfied_by"]
        # Every category has a checked source in at least one of its markets.
        assert any(category_for_market(entry["id"], m)["sources"] for m in entry["markets"]), entry["id"]
        for item in entry["sources"] + entry["papers"]:
            assert item["url"].startswith("https://"), item
    # Retracted: Bai, Bali and Wen (2019, JFE), 10.1016/j.jfineco.2018.08.002.
    urls = {p["url"] for e in DATA_CATEGORIES for p in e["papers"]}
    assert "https://doi.org/10.1016/j.jfineco.2018.08.002" not in urls


def test_planner_sees_the_stored_fields(tmp_path, monkeypatch):
    from quantaalpha.pipeline import planning

    store = _store(tmp_path, {"a": ["close", "funding_rate"]})
    monkeypatch.setenv("QLIB_DATA_DIR", str(store))
    seen = {}

    class Fake:
        def build_messages_and_create_chat_completion(self, user_prompt, system_prompt, **_):
            seen["prompt"] = user_prompt
            return '{"directions": ["a", "b"]}'

    monkeypatch.setattr(planning, "APIBackend", Fake)
    prompt_file = Path(planning.__file__).parent / "prompts" / "planning_prompts.yaml"
    assert planning.generate_parallel_directions("funding carry", 2, prompt_file) == ["a", "b"]
    assert "$funding_rate" in seen["prompt"] and "ONLY these daily fields" in seen["prompt"]


@pytest.mark.parametrize("mode, has_fundamentals", [("crypto", False), ("us", True)])
def test_fallback_directions_respect_the_market(monkeypatch, mode, has_fundamentals):
    from quantaalpha.pipeline import planning

    monkeypatch.setenv("MARKET_MODE", mode)
    directions = planning._fallback_directions("x", 8)
    assert any("fundamentals" in d for d in directions) is has_fundamentals
    assert not any("price-to-book" in d or "intraday" in d for d in directions)


def test_market_without_a_checked_source_gets_searches_not_guesses():
    result = df.assemble("patent citations predict returns", "cn", ["close", "total_mv"], None)
    concept = result["concepts"][0]
    assert concept["status"] == "missing" and concept["categories"][0]["sources"] == []
    assert [link["name"] for link in concept["searchLinks"]] == ["Google Scholar", "SSRN", "GitHub"]


def test_the_predicted_return_is_not_counted_as_signal_data():
    llm = {"concepts": [
        {"concept": "analyst EPS forecast revisions", "status": "missing", "category_ids": ["analyst_forecasts"]},
        {"concept": "subsequent stock returns", "status": "available", "fields": ["ret_total", "delist_return"]},
    ]}
    result = df.assemble("Analyst revisions predict returns", "us", US_FIELDS + ["delist_return"], llm)
    assert [c["concept"] for c in result["concepts"]] == ["analyst EPS forecast revisions"]
    assert result["verdict"] == "unavailable" and result["runDirection"] is None
    # A return used to build the signal (e.g. reversal) still counts.
    kept = df.assemble("reversal", "us", US_FIELDS,
                       {"concepts": [{"concept": "past 5-day return", "status": "available", "fields": ["ret_total"]}]})
    assert kept["verdict"] == "feasible"


def test_proxies_are_labelled_as_proxies_in_the_run_direction():
    llm = {"concepts": [
        {"concept": "gross profitability", "status": "available", "fields": ["gross_profitability_q"]},
        {"concept": "firm size", "status": "proxy", "fields": ["atq"], "note": "assets, not market value"},
    ]}
    text = df.assemble("small profitable firms", "us", US_FIELDS + ["atq"], llm)["runDirection"]
    assert "Fields that measure this idea: $gross_profitability_q." in text
    assert "Weaker proxy only for firm size: $atq (assets, not market value)." in text


def test_papers_are_filtered_by_market():
    cites = lambda m: [p["citation"] for p in category_for_market("market_equity", m)["papers"]]
    assert not any("China" in c or "cryptocurrency" in c for c in cites("us"))
    assert any("cryptocurrency" in c for c in cites("crypto"))
    assert any("China" in c for c in cites("cn"))

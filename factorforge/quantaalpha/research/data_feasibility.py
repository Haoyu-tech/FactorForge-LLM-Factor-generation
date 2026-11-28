"""Check whether a research direction can be tested with the data on disk.

The mining loop always turns a direction into formulas over the stored fields.
When the direction needs data the store does not hold (analyst forecasts,
options, on-chain flows, ...), the LLM silently substitutes a price or volume
stand-in and the run tests something other than what was asked. This module
answers first: it lists the stored fields that measure each part of the idea,
names what is missing, and attaches sources for the missing data from
``source_registry`` (never from the LLM).

Run as a module so the LLM settings are read from the environment the backend
prepares for mining:

    python -m quantaalpha.research.data_feasibility --direction-file d.txt \
        --market-mode us --qlib-dir /path/to/qlib --output result.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

from quantaalpha.research.source_registry import (
    CATEGORIES_BY_ID,
    DATA_CATEGORIES,
    category_for_market,
    replication_resources,
)

MARKET_NAMES = {
    "us": "US equities (historical S&P 500 members, CRSP prices and point-in-time Compustat quarterly data)",
    "cn": "China A shares (local DuckDB daily data, Tushare-style fields)",
    "crypto": "Binance USD-M USDT perpetual futures (daily bars and funding)",
}

# Plain descriptions for the fields the three store builders write. A stored
# field without an entry is still listed, by name only.
FIELD_DESCRIPTIONS = {
    "open": "daily open price", "high": "daily high price", "low": "daily low price",
    "close": "daily close price (split-adjusted)", "volume": "daily traded volume",
    "factor": "price adjustment factor", "change": "close-to-close return",
    "ret_total": "total return including dividends (CRSP RET)",
    "delist_return": "CRSP delisting return on the delisting date",
    "return": "close-to-close return",
    # US Compustat quarterly, point in time from rdq
    "atq": "total assets (quarterly)", "saleq": "sales (quarterly)", "niq": "net income (quarterly)",
    "ceqq": "common (book) equity (quarterly)", "invtq": "inventories", "rectq": "receivables",
    "ppentq": "net property, plant and equipment", "ltq": "total liabilities", "req": "retained earnings",
    "oiadpq": "operating income after depreciation",
    "roa_q": "return on assets", "roe_q": "return on equity", "gross_profitability_q": "gross profit / assets",
    "operating_profitability_q": "operating profit / book equity", "leverage_q": "liabilities / equity",
    "cash_to_assets_q": "cash / assets", "asset_growth_q": "asset growth", "sales_growth_q": "sales growth",
    "earnings_growth_q": "earnings growth", "operating_income_growth_q": "operating income growth",
    "inventory_change_to_assets_q": "change in inventory / assets",
    "receivables_change_to_assets_q": "change in receivables / assets",
    "ppent_change_to_assets_q": "change in PP&E / assets", "inventory_to_sales_q": "inventory / sales",
    "receivables_to_sales_q": "receivables / sales", "gross_margin_q": "gross margin",
    "operating_margin_q": "operating margin", "liabilities_to_assets_q": "liabilities / assets",
    "retained_earnings_to_assets_q": "retained earnings / assets",
    "report_lag_days": "days from fiscal quarter end to the earnings report date (rdq)",
    "fundamental_age_days": "days since the latest fundamentals became public",
    "gsector": "GICS sector", "ggroup": "GICS industry group", "gind": "GICS industry",
    "gsubind": "GICS sub-industry",
    # China A shares
    "amount": "traded value", "turnover_rate": "turnover rate", "turnover_rate_f": "free-float turnover rate",
    "volume_ratio": "volume ratio versus recent average", "pe": "price / earnings", "pe_ttm": "price / TTM earnings",
    "pb": "price / book", "ps_ttm": "price / TTM sales", "total_share": "total shares",
    "float_share": "floating shares", "free_share": "free-float shares", "total_mv": "total market value",
    "circ_mv": "circulating market value", "is_st": "ST flag on that date",
    "listing_age_days": "trading days since listing", "roe": "return on equity", "roa": "return on assets",
    "grossprofit_margin": "gross margin", "netprofit_margin": "net margin", "debt_to_assets": "debt / assets",
    "assets_turn": "asset turnover", "current_ratio": "current ratio", "q_sales_yoy": "quarterly sales growth y/y",
    "basic_eps_yoy": "EPS growth y/y", "q_ocf_to_sales": "operating cash flow / sales", "roic": "return on invested capital",
    "assets_yoy": "asset growth y/y", "sw_l1": "Shenwan level-1 industry", "sw_l2": "Shenwan level-2 industry",
    "sw_l3": "Shenwan level-3 industry",
    # Crypto
    "quote_volume": "traded value in USDT", "trade_count": "number of trades",
    "taker_buy_volume": "taker (aggressive) buy volume", "taker_buy_quote_volume": "taker buy value in USDT",
    "taker_buy_ratio": "taker buy volume / total volume", "funding_rate": "daily sum of perpetual funding rates",
    "market_group": "single market-wide group (no sectors)",
}

from quantaalpha.data.ibes_adapter import FIELD_DESCRIPTIONS as _IBES_DESCRIPTIONS

FIELD_DESCRIPTIONS.update(_IBES_DESCRIPTIONS)

STATUS_ORDER = ("available", "proxy", "missing", "wrong_market")


def store_fields(qlib_dir: str | os.PathLike | None) -> list[str]:
    """Return the field names that exist as ``features/<instrument>/<field>.day.bin``."""
    if not qlib_dir:
        return []
    features = Path(qlib_dir).expanduser() / "features"
    if not features.is_dir():
        return []
    names: set[str] = set()
    with os.scandir(features) as instruments:
        for instrument in instruments:
            if not instrument.is_dir():
                continue
            with os.scandir(instrument.path) as files:
                for entry in files:
                    if entry.name.endswith(".day.bin"):
                        names.add(entry.name[: -len(".day.bin")])
    return sorted(names)


def field_catalog_text(fields: list[str]) -> str:
    return "\n".join(
        f"${name}: {FIELD_DESCRIPTIONS[name]}" if name in FIELD_DESCRIPTIONS else f"${name}"
        for name in fields
    )


def keyword_hits(direction: str) -> list[str]:
    """Categories whose keywords appear in the direction, in registry order."""
    text = " " + re.sub(r"\s+", " ", direction.lower()) + " "
    hits = []
    for entry in DATA_CATEGORIES:
        for keyword in entry["keywords"]:
            word = keyword.lower()
            # ASCII keywords must match whole words, plural allowed ("option"
            # matches "options" but not "optional"); CJK has no word boundaries.
            if word.isascii():
                if re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?:s|es)?(?![a-z0-9])", text):
                    hits.append(entry["id"])
                    break
            elif word in text:
                hits.append(entry["id"])
                break
    return hits


def category_status(category_id: str, market_mode: str, fields: list[str]) -> str:
    entry = CATEGORIES_BY_ID[category_id]
    if market_mode not in entry["markets"]:
        return "wrong_market"
    return "available" if set(entry["satisfied_by"]) & set(fields) else "missing"


SYSTEM_PROMPT = """You check whether a factor research direction can be tested with one local database.
You are strict: a field counts only if it measures the concept itself. You never invent field names,
data sets, papers or URLs. Reply with JSON only."""

USER_TEMPLATE = """Research direction from the user:
<<<
{direction}
>>>

Market: {market}

These are the ONLY fields in the database (daily panel, one value per instrument per date):
{catalog}

Data categories that the system can attach verified sources to (id: description):
{categories}

A keyword scan flagged these categories in the direction: {hits}

Task:
1. List every distinct data concept the direction needs to BUILD ITS SIGNAL (for example "analyst
   forecast revisions", "short-term price reversal", "firm size"). Do not list the future return the
   signal is meant to predict: the system always supplies it.
2. For each concept choose a status:
   - "available": one or more listed fields measure it directly. Name them in "fields".
   - "proxy": no field measures it, but listed fields give a weaker stand-in. Name them and say in
     "note" what the proxy misses. Use this sparingly.
   - "missing": nothing in the list measures it. Put the matching category ids in "category_ids"
     (use [] if none fits) and give 2-5 "search_terms" someone could use to find the data.
   - "wrong_market": the concept belongs to a different market (for example on-chain flows for US
     stocks, or GICS sectors for crypto).
3. "suggested_direction": rewrite the direction so it uses only the listed fields while keeping its
   economic idea. Use an empty string if the idea cannot survive without the missing data.
4. "reply": 2-4 plain sentences to the user, in the language of the direction, saying what can be
   tested, what cannot and why. Do not mention papers or websites; the system adds verified ones.

Return exactly this JSON:
{{"verdict": "feasible" | "partial" | "unavailable",
  "reply": "...",
  "concepts": [{{"concept": "...", "status": "available" | "proxy" | "missing" | "wrong_market",
                 "fields": ["$field"], "category_ids": ["id"], "search_terms": ["..."], "note": "..."}}],
  "suggested_direction": "..."}}"""


def build_prompt(direction: str, market_mode: str, fields: list[str], hits: list[str]) -> str:
    categories = "\n".join(
        f"{entry['id']}: {entry['label']}"
        + ("" if market_mode in entry["markets"] else " (not for this market)")
        for entry in DATA_CATEGORIES
    )
    return USER_TEMPLATE.format(
        direction=direction.strip(),
        market=MARKET_NAMES.get(market_mode, market_mode),
        catalog=field_catalog_text(fields) or "(no fields found)",
        categories=categories,
        hits=", ".join(hits) if hits else "none",
    )


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    body = fence.group(1) if fence else text
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _search_links(terms: list[str]) -> list[dict]:
    query = " ".join(terms[:5]).strip()
    if not query:
        return []
    encoded = quote_plus(query)
    return [
        {"name": "Google Scholar", "url": f"https://scholar.google.com/scholar?q={encoded}"},
        {"name": "SSRN", "url": f"https://papers.ssrn.com/sol3/results.cfm?txtKey_Words={encoded}"},
        {"name": "GitHub", "url": f"https://github.com/search?q={encoded}&type=repositories"},
    ]


TARGET_FIELDS = {"ret_total", "delist_return", "change", "return"}
TARGET_WORDS = ("subsequent", "future", "forward", "next-period", "next period", "realized return",
                "未来收益", "后续收益", "下期收益")


def _is_prediction_target(raw: dict) -> bool:
    """True for a concept that is only the future return being predicted.

    Returns always exist, so counting them as available data would turn a
    direction whose every signal is missing into a "partial" one.
    """
    name = str(raw.get("concept", "")).lower()
    fields = {str(f).strip().lstrip("$") for f in raw.get("fields") or []}
    return bool(fields) and fields <= TARGET_FIELDS and any(word in name for word in TARGET_WORDS)


def _concept(name: str, status: str, fields: list[str], invented: list[str], note: str | None,
             category_ids: list[str], terms: list[str], market_mode: str) -> dict:
    categories = [category_for_market(cid, market_mode) for cid in category_ids]
    links: list[dict] = []
    if status in {"missing", "wrong_market"} and not any(c["sources"] for c in categories):
        # No checked source on file for this market: offer searches, never a guessed link.
        if not terms:
            terms = [name]
        links = _search_links(terms)
    return {
        "concept": name,
        "status": status,
        "fields": fields,
        "inventedFields": invented,
        "note": note,
        "categories": categories,
        "searchTerms": terms,
        "searchLinks": links,
    }


def _verdict(concepts: list[dict]) -> str:
    statuses = {concept["status"] for concept in concepts}
    if not concepts:
        return "unclear"
    if statuses <= {"available"}:
        return "feasible"
    if "available" in statuses or "proxy" in statuses:
        return "partial"
    return "unavailable"


def assemble(direction: str, market_mode: str, fields: list[str], llm_result: dict | None,
             llm_error: str | None = None) -> dict:
    """Validate the LLM answer against the store and attach registry sources."""
    hits = keyword_hits(direction)
    stored = set(fields)
    concepts: list[dict] = []
    referenced: set[str] = set()

    for raw in (llm_result or {}).get("concepts") or []:
        if not isinstance(raw, dict) or not str(raw.get("concept", "")).strip():
            continue
        if _is_prediction_target(raw):
            continue
        status = str(raw.get("status", "missing")).strip().lower()
        if status not in STATUS_ORDER:
            status = "missing"
        named = [str(f).strip().lstrip("$") for f in raw.get("fields") or [] if str(f).strip()]
        valid = [f for f in named if f in stored]
        invented = [f for f in named if f not in stored]
        note = str(raw.get("note") or "").strip()
        if status in {"available", "proxy"} and not valid:
            # The LLM named fields that do not exist; do not let that pass as data.
            status = "missing"
            note = (note + " " if note else "") + "The fields named for this do not exist in the database."
        category_ids = [c for c in raw.get("category_ids") or [] if c in CATEGORIES_BY_ID]
        referenced.update(category_ids)
        terms = [str(t).strip() for t in raw.get("search_terms") or [] if str(t).strip()]
        concepts.append(_concept(
            str(raw["concept"]).strip(), status, valid if status in {"available", "proxy"} else [],
            invented, note or None, category_ids if status in {"missing", "wrong_market"} else [],
            terms, market_mode,
        ))

    # A keyword match the LLM did not account for still counts when its data is
    # absent: letting it pass silently is how price/volume proxies slip in.
    for cid in hits:
        if cid in referenced:
            continue
        status = category_status(cid, market_mode, fields)
        if status == "available":
            continue
        concepts.append(_concept(
            CATEGORIES_BY_ID[cid]["label"], status, [], [],
            "Found by keyword match in the direction"
            + ("." if llm_result is None else "; the model check did not list it."),
            [cid], [], market_mode,
        ))

    verdict = _verdict(concepts)
    if llm_result is None and verdict == "unavailable":
        # A keyword scan only sees the data the text names, not the parts the
        # stored fields do cover, so it cannot rule the whole direction out.
        verdict = "partial"
    reply = str((llm_result or {}).get("reply") or "").strip()
    if not reply:
        reply = _fallback_reply(verdict, concepts)
    suggestion = str((llm_result or {}).get("suggested_direction") or "").strip()
    missing = [c for c in concepts if c["status"] in {"missing", "wrong_market"}]
    usable = sorted({f for c in concepts if c["status"] == "available" for f in c["fields"]})
    proxies = [c for c in concepts if c["status"] == "proxy"]

    return {
        "verdict": verdict,
        "reply": reply,
        "marketMode": market_mode,
        "storeFieldCount": len(fields),
        "storeFields": fields,
        "concepts": concepts,
        "suggestedDirection": suggestion or None,
        "runDirection": run_direction(direction, verdict, usable, missing, proxies),
        "replication": replication_resources(market_mode) if missing else None,
        "keywordHits": hits,
        "llm": {"used": llm_result is not None, "error": llm_error},
    }


def _fallback_reply(verdict: str, concepts: list[dict]) -> str:
    missing = [c["concept"] for c in concepts if c["status"] in {"missing", "wrong_market"}]
    if verdict == "unclear":
        return ("The language model check did not answer and no known data need was found in the text, "
                "so the data requirements of this direction are unknown.")
    if missing:
        return ("This direction needs data that is not in the database: " + "; ".join(missing) + ". "
                "The model check did not answer, so the rest of the idea was not checked against the stored fields.")
    return "The direction can be built from the stored fields."


def run_direction(direction: str, verdict: str, usable: list[str], missing: list[dict],
                  proxies: list[dict] | None = None) -> str | None:
    """The direction handed to mining, with the data check written into it."""
    if verdict == "unavailable":
        return None
    notes = []
    if usable:
        notes.append("Fields that measure this idea: " + ", ".join(f"${f}" for f in usable) + ".")
    for proxy in proxies or []:
        notes.append(
            f"Weaker proxy only for {proxy['concept']}: " + ", ".join(f"${f}" for f in proxy["fields"])
            + (f" ({proxy['note']})" if proxy.get("note") else "") + "."
        )
    if missing:
        notes.append(
            "Not in the database, so do not approximate them with price or volume stand-ins: "
            + "; ".join(c["concept"] for c in missing) + "."
        )
    if not notes:
        return direction.strip()
    return "\n".join([direction.strip(), "", "[Data check]", *notes])


def check_direction(direction: str, market_mode: str, qlib_dir: str | None, use_llm: bool = True) -> dict:
    fields = store_fields(qlib_dir)
    if not fields:
        result = assemble(direction, market_mode, fields, None, "No Qlib fields found")
        result["verdict"] = "no_data"
        result["reply"] = (
            f"No data store was found for this market at {qlib_dir or '(not configured)'}. "
            "Build it on the Settings data page before checking or mining."
        )
        result["runDirection"] = None
        return result
    if not use_llm:
        return assemble(direction, market_mode, fields, None, "LLM check disabled")
    llm_result, llm_error = None, None
    try:
        from quantaalpha.llm.client import APIBackend

        response = APIBackend().build_messages_and_create_chat_completion(
            user_prompt=build_prompt(direction, market_mode, fields, keyword_hits(direction)),
            system_prompt=SYSTEM_PROMPT,
            json_mode=False,
        )
        llm_result = _extract_json(response)
        if llm_result is None:
            llm_error = "The language model reply was not valid JSON"
    except Exception as exc:  # the keyword check still answers
        llm_error = f"{type(exc).__name__}: {exc}"
    return assemble(direction, market_mode, fields, llm_result, llm_error)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--direction-file", required=True)
    parser.add_argument("--market-mode", choices=sorted(MARKET_NAMES), required=True)
    parser.add_argument("--qlib-dir", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args(argv)
    direction = Path(args.direction_file).read_text(encoding="utf-8")
    result = check_direction(direction, args.market_mode, args.qlib_dir, use_llm=not args.no_llm)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

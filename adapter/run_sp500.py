# -*- coding: utf-8 -*-
"""
run_sp500.py - LLM factor mining on the S&P 500 monthly panel.

A self-contained propose -> evaluate -> evolve loop that reuses:
  - QuantaAlpha's LLM client  (quantaalpha.llm.client.APIBackend, reads .env)
  - QuantaAlpha's parser+operators (via adapter/sp500_loader.compute_factor)
  - our qlib-free scorer       (adapter/evaluate_ic.summary -> RankIC/ICIR/IC_t)

This deliberately bypasses QuantaAlpha's qlib-bound backtest (runner.py needs a
qlib dataset). It captures the same essence: the LLM writes factor expressions,
they are scored by RankIC vs next-month return, and the best ones seed the next
round. Runs the moment QuantaAlpha/.env has a working API key.

Usage:
  conda activate llm-factor
  python adapter/run_sp500.py --direction "quality-value interactions in large caps" \
      --rounds 3 --per-round 6 --start 1972-01-01
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ADAPTER = Path(__file__).resolve().parent
ROOT = ADAPTER.parent
for p in (str(ADAPTER), str(ROOT / "QuantaAlpha")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
if load_dotenv is not None:
    load_dotenv(ROOT / "QuantaAlpha" / ".env")

from sp500_loader import available_fields, compute_factor          # noqa: E402
from evaluate_ic import summary                                     # noqa: E402
from llm_factor.config import path, sample, search                   # noqa: E402
from llm_factor.grammar import get_grammar                            # noqa: E402
from llm_factor.ledger import CandidateLedger                         # noqa: E402
from llm_factor.manifest import default_input_paths, run_id, write_manifest  # noqa: E402


def _field_dictionary(pool: list[str]) -> str:
    """One-line JKP definition per pool field: '$name: definition' (field-list metadata,
    not example factors). Fields missing from the dictionary are listed with no gloss."""
    try:
        defs = json.loads(path("factor_dictionary").read_text(encoding="utf-8"))
    except Exception:
        defs = {}
    lines = []
    for f in pool:
        d = defs.get(f[1:], "")
        lines.append(f"  {f}: {d}" if d else f"  {f}")
    return "\n".join(lines)


def build_scenario() -> str:
    prose = (ADAPTER / "scenario_sp500.md").read_text(encoding="utf-8")
    # Strip editor-facing HTML comments (e.g. the standing-rule note) so they never
    # reach the LLM; the prompt the model sees stays clean.
    prose = re.sub(r"<!--.*?-->", "", prose, flags=re.DOTALL).strip()
    grammar = get_grammar()
    # Field pool must equal the GP leaf pool exactly (fair LLM-vs-GP comparison):
    # both draw from grammar.leaf_fields, so neither side sees a field the other cannot use.
    pool = grammar.leaf_fields(available_fields())
    fields = " ".join(pool)
    return (f"{prose}\n\nAUTHORITATIVE FIELD LIST (use ONLY these; this list supersedes any "
            f"field named in the prose above): {fields}\n\n"
            f"FIELD DICTIONARY (one-line meaning of each field; use for economic reasoning):\n"
            f"{_field_dictionary(pool)}\n\n"
            f"PRIMARY OPERATOR GRAMMAR: {grammar.name}\n"
            f"OPERATORS: {grammar.operator_prompt()}")


def _backend():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key or key.startswith("<"):
        sys.exit(
            "ERROR: no API key. Fill QuantaAlpha/.env. To use CLAUDE via Anthropic's "
            "OpenAI-compatible endpoint (openai SDK is already installed in the llm-factor env):\n"
            "  OPENAI_API_KEY=<your anthropic key sk-ant-...>\n"
            "  OPENAI_BASE_URL=https://api.anthropic.com/v1/\n"
            "  CHAT_MODEL=claude-opus-4-8\n"
            "  REASONING_MODEL=claude-opus-4-8\n"
            "See QuantaAlpha/.env.claude.example.")
    from quantaalpha.llm.client import APIBackend
    return APIBackend()


def _ask_json(backend, system_prompt, user_prompt) -> list:
    try:
        from quantaalpha.llm.client import robust_json_parse as _parse
    except Exception:
        _parse = json.loads
    resp = backend.build_messages_and_create_chat_completion(
        user_prompt=user_prompt, system_prompt=system_prompt, json_mode=False)
    try:
        data = _parse(resp)
    except Exception:
        return []
    return data.get("factors", data) if isinstance(data, dict) else (data or [])


SYS = ("You are a quantitative equity researcher mining cross-sectional alpha "
       "factors for monthly S&P 500 prediction. Follow the scenario exactly and "
       "output STRICT JSON: {\"factors\":[{\"name\":..,\"expression\":..,\"rationale\":..}]}. "
       "Expressions must use only the listed $fields and the PRIMARY OPERATOR GRAMMAR.")


def propose_prompt(scenario, direction, n):
    return (f"{scenario}\n\nResearch direction: {direction}\n"
            f"Propose {n} DIVERSE candidate factors (mix data types). Include a balanced mix of:\n"
            f"- simple rank-sum composites,\n"
            f"- multiplicative interactions using `*`,\n"
            f"- ratio/normalization ideas using `/`, and\n"
            f"- time-series interactions using allowed TS_* operators.\n"
            f"Keep each expression parsimonious and economically interpretable. JSON only.")


def evolve_prompt(scenario, direction, n, top):
    lib = "\n".join(f"  IC_t={r['IC_t']:+.2f} IC={r['IC']:+.4f}  {r['expression']}" for r in top)
    return (f"{scenario}\n\nResearch direction: {direction}\n"
            f"Here are the best factors so far (by |IC_t|):\n{lib}\n\n"
            f"Propose {n} NEW factors that improve on these by mutation (tweak windows/ops) "
            f"or crossover (combine two). Add structural diversity: at least some candidates "
            f"should use `*`, `/`, and allowed TS_* operators rather than only rank-sums. "
            f"Aim for higher |IC_t| without losing economic rationale. JSON only.")


def evaluate(items, start, seen, ledger=None, round_id=None):
    out = []
    for it in items:
        if not isinstance(it, dict):
            if ledger:
                ledger.append(round=round_id, status="malformed", raw=it)
            continue
        expr = (it.get("expression") or "").strip()
        rationale = (it.get("rationale") or "").strip()
        base_record = {
            "round": round_id,
            "source": "llm",
            "name": it.get("name", ""),
            "expression": expr,
            "rationale": rationale,
        }
        if not expr:
            if ledger:
                ledger.append(**base_record, status="missing_expression")
            continue
        if expr in seen:
            if ledger:
                ledger.append(**base_record, status="duplicate")
            continue
        seen.add(expr)
        if not rationale:                   # economic rationale is mandatory
            print(f"    skip (no economic rationale): {expr[:50]}")
            if ledger:
                ledger.append(**base_record, status="missing_rationale")
            continue
        try:
            compute_factor(expr)            # parse/compute guard
            m = summary(expr, start=start)
        except Exception as e:
            print(f"    skip (error): {expr[:60]}  [{str(e)[:50]}]")
            if ledger:
                ledger.append(**base_record, status="error", error=str(e))
            continue
        if m["n_months"] < 12 or m["IC"] != m["IC"]:   # nan guard
            if ledger:
                ledger.append(**base_record, status="insufficient_data", metrics=m)
            continue
        m["name"] = it.get("name", "") or f"f{len(out)}"
        m["expression"] = expr
        m["rationale"] = rationale
        out.append(m)
        if ledger:
            ledger.append(**base_record, status="accepted", metrics=m)
        print(f"    IC_t={m['IC_t']:+.2f} IC={m['IC']:+.4f} ICIR={m['ICIR']:+.3f} LS_SR={m['LS_SR']:+.2f}  {expr}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--direction", required=True)
    ap.add_argument("--rounds", type=int, default=search("default_rounds", 3))
    ap.add_argument("--per-round", type=int, default=search("default_per_round", 6))
    ap.add_argument("--start", default=sample("start", "1972-01-01"))
    ap.add_argument("--split", default=sample("split", "2000-12-31"), help="train/test OOS split date")
    ap.add_argument("--top-k", type=int, default=search("default_top_k", 8), help="best factors fed back each round")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    scenario = build_scenario()
    backend = _backend()
    seen, library = set(), []
    rid = run_id("llm_mining")
    ledger = CandidateLedger(rid)

    print(f"== mining: '{args.direction}'  ({args.rounds} rounds x {args.per_round}) ==")
    for rnd in range(args.rounds):
        if rnd == 0:
            prompt = propose_prompt(scenario, args.direction, args.per_round)
        else:
            top = sorted(library, key=lambda r: abs(r["IC_t"]), reverse=True)[: args.top_k]
            prompt = evolve_prompt(scenario, args.direction, args.per_round, top)
        print(f"\n-- round {rnd} --")
        items = _ask_json(backend, SYS, prompt)
        library += evaluate(items, args.start, seen, ledger=ledger, round_id=rnd)

    library.sort(key=lambda r: abs(r["IC_t"]), reverse=True)
    out = Path(args.out) if args.out else (
        ROOT / "data" / f"mined_factors_{datetime.now():%Y%m%d_%H%M%S}.json")
    out.write_text(json.dumps(library, indent=2), encoding="utf-8")

    print(f"\n== top factors by IC_t ({len(library)} total) ==")
    print(f"{'IC':>8}{'IC_t':>7}{'ICIR':>7}{'LS_SR':>7}  expression")
    for r in library[:15]:
        print(f"{r['IC']:>8.4f}{r['IC_t']:>7.2f}{r['ICIR']:>7.3f}{r['LS_SR']:>7.2f}  {r['expression']}")
    print(f"\nsaved -> {out}")
    print(f"candidate ledger -> {ledger.path}")

    # rigorous gate for EVERY mined factor: OOS + FF3 alpha + monotonicity + viz folder
    from factor_lab import run_report
    factors = {r["name"]: (r["expression"], r["rationale"]) for r in library}
    if factors:
        print("\n== running full evaluation gate (OOS / FF3 / monotonicity / charts) ==")
        gate_dir, _ = run_report(factors, start=args.start, split=args.split)
        write_manifest(
            gate_dir,
            run_name=rid,
            params={
                "direction": args.direction,
                "rounds": args.rounds,
                "per_round": args.per_round,
                "start": args.start,
                "split": args.split,
            "top_k": args.top_k,
                "operator_grammar": get_grammar().name,
                "candidate_ledger": str(ledger.path),
            },
            inputs={**default_input_paths(), "candidate_ledger": ledger.path, "mined_factors": out},
            notes="LLM mining run followed by the strict factor_lab evaluation gate.",
        )


if __name__ == "__main__":
    main()


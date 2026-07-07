# LLM-Factor: Auditable Factor Discovery with Large Language Models

**Can large language models generate economically interpretable equity factors
that survive modern empirical asset-pricing validation?**

This repository builds an LLM-guided factor-discovery pipeline on a monthly
S&P 500 panel (1972–2025) and subjects every proposed factor to a pre-specified,
asset-pricing-grade validation gate — value-weighted long–short portfolios,
Fama–French five-factor + momentum (FF5+UMD) Newey–West alphas, out-of-sample
and walk-forward tests, spanning regressions against a published anomaly zoo,
firm-level Fama–MacBeth regressions, and multiple-testing haircuts.

The central design principle is **auditability**: the LLM is used as a
*disciplined economic hypothesis generator*, not as a black-box return
predictor. Candidate generation is separated from validation by an append-only
ledger, a locked discovery/OOS split, and a common expression grammar shared by
the LLM and a mechanical genetic-programming baseline.

---

## Thesis in one paragraph

A flexible search device can always manufacture profitable-looking signals
in-sample; return-predictability tests are notoriously vulnerable to data
mining. So the interesting question is not "can an LLM find a high-IC factor"
(it can, and so can random search), but "can an LLM produce economically
structured factors that *survive a strict out-of-sample asset-pricing gate*?"
Our headline finding: a full-grammar **genetic-programming baseline beats the
LLM in-sample** (higher selection-window RankIC) yet its winner **collapses
out-of-sample and fails the gate**, while the LLM's economically-motivated
mispricing/financing-discipline factors **pass the full+OOS gate**. The LLM's
edge is not higher IC — it is producing factors whose economic prior makes them
robust to rigorous OOS scrutiny.

---

## Headline results

Validated LLM factors (value-weighted FF5+UMD alpha, Newey–West *t*, full sample
1972–2025 / OOS post-2000):

| Factor | Expression (schematic) | Ann. VW FF5+UMD α | Full *t* | OOS *t* |
|---|---|---|---|---|
| `mispricing_combo` | `RANK($mispricing_perf) + RANK($mispricing_mgmt)` | 8.9% | 3.93 | 2.96 |
| `mispr_fin_quality` | mispricing − issuance − asset-growth + profitability | 7.3% | 3.50 | 2.75 |
| `mispr_fin_disc` | mispricing − equity-issuance − asset-growth | 7.5% | 3.41 | 2.31 |
| `financing_reversal_guard` | − issuance + momentum − short-reversal | 11.7% | 4.09 | 1.97 |

**Horse race (LLM vs. full-grammar GP on the same 124-field pool):** GP wins
in-sample (selection RankIC ≈ 0.049 > LLM ≈ 0.039, reaching the LLM's level
within ~180 evaluations) but its uninterpretable winner collapses OOS
(IC ≈ 0.006) and **fails** the OOS gate (*t* = 1.21); the LLM survivors pass.
See `results/formal/horse_race_scatter.png`.

**The failures are part of the evidence.** `qual_val_mom` has strong full-sample
alpha but its OOS VW alpha *t* falls to ~1.94 and it fails the gate;
`fin_inv_discipline` has strong firm-level Fama–MacBeth predictability but weak
value-weighted OOS alpha (an equal-weight / smaller-name effect, and fully
spanned by the anomaly zoo). The pipeline is selective, and rejected candidates
stay in the ledger.

---

## Why this is a contribution

"Use an LLM to synthesize formulaic factors" is by now an established subfield
(AlphaAgent, Alpha-GPT, Chain-of-Alpha, FactorMAD, plus a survey and a
benchmark). What existing work mostly does *not* do is bring **empirical
asset-pricing rigor** (value-weighting + FF5/q-factor Newey–West alphas +
Harvey–Liu–Zhu *t*>3 multiple testing + spanning the *published* factor zoo) to
LLM factor mining, in a **US-monthly, large-cap, survivorship-free** setting,
with a fully **auditable** discovery protocol. That intersection is the gap this
project targets. See `docs/PAPER_DRAFT.md` for the working paper.

---

## Design principles

1. **Locked discovery / OOS split.** The discovery sample ends 2000-12-31; the
   post-2000 period is held out for validation. The LLM never sees OOS
   performance during generation, prompt revision, or selection.
2. **Append-only candidate ledger.** Every candidate — including parse errors,
   duplicates, missing rationales, and failed factors — is recorded
   (`results/candidate_ledgers/`). This is the audit trail for researcher
   degrees of freedom, and it feeds the multiple-testing budget.
3. **Shared grammar.** LLM proposals and the GP baseline pass through the
   *identical* expression parser, operator set, and field pool
   (`grammar.leaf_fields`), so the comparison isolates "economic synthesis" from
   "brute-force symbolic search."
4. **Discovery-prompt policy (frozen).** The discovery prompt contains exactly
   three parts and nothing else: (a) data/rules description, (b) field list,
   (c) operator glossary. **No worked example factors and no in-sample
   performance numbers** — both would leak winners and anchor the LLM's
   structure, opening data-snooping attack surfaces. See `PROJECT_STATE.md`.
5. **Economic rationale required.** Each candidate must carry an economic
   mechanism (mispricing, limits to arbitrage, financing/investment discipline,
   quality, risk, underreaction) *before* it is evaluated OOS.

---

## Repository structure

```
LLM-Factor/
├── README.md                     # this file
├── PROJECT_STATE.md              # state model + frozen discovery-prompt policy
├── CHANGELOG.md                  # dated research log
├── docs/
│   ├── PAPER_DRAFT.md            # working paper
│   ├── TOP_TIER_EMPIRICAL_DESIGN.md
│   ├── LLM_GENERATION_PROTOCOL.md
│   └── EXTENDED_FACTOR_POOL.md
├── configs/
│   ├── llm_factor.json           # paths, sample splits, thresholds, grammars
│   ├── factors.json              # curated factor registry (name/expr/rationale)
│   ├── kelly_usable_factors.json # single source of truth: 120 usable chars
│   └── factor_dictionary.json    # one-line JKP definition per pool field
├── data/                         # built monthly panels (parquet) + coverage csv
├── llm_factor/                   # package: grammar, factors, ledger, manifest
├── adapter/                      # the pipeline (see below)
├── results/                      # run outputs, ledgers, formal deliverable
└── QuantaAlpha/                  # upstream repo (grammar/parser reused)
```

### The pipeline (`adapter/`)

**Data construction**
- `build_sp500_membership.py` → point-in-time S&P 500 add/drop spells from CRSP
  constituent dates (no survivorship bias).
- `build_sp500_monthly_full.py` → full official universe (~500/month) monthly
  price/volume panel.
- `build_sp500_monthly_kelly.py` → **default panel**: full universe + 120 usable
  Kelly-153 characteristics (value/quality/momentum/issuance/risk/liquidity/
  mispricing/…), 128 `$`-features, 1972–2025.

**Discovery**
- `sp500_loader.py` → qlib-free replacement for the upstream data loader + factor
  computation; word-boundary `$field` substitution (fixes an upstream
  `str.replace` bug on overlapping names).
- `run_sp500.py` → self-contained propose → evaluate → evolve loop; builds the
  scenario prompt from `scenario_sp500.md` + live `available_fields()`.
- `gp_search.py`, `gp_search_full.py` → genetic-programming baselines over the
  same grammar (the mechanical-search horse-race opponent).

**Validation suite** (all emit Markdown + LaTeX `booktabs` + CSV)
- `factor_lab.py` → the strict gate: EW + **value-weighted** long–short, benchmark
  ladder CAPM→FF3→Carhart4→FF5→**FF5+UMD** (Newey–West), decile monotonicity,
  full + OOS split, PASS/FAIL verdict, 4-panel chart.
- `spanning.py` → regress a factor on its own components and on a 14-theme JKP
  composite anomaly zoo; a significant intercept = genuine increment.
- `walk_forward.py` → expanding-window 3-year OOS blocks (1990–2025).
- `fama_macbeth.py` → firm-level cross-sectional regressions with size/value/
  momentum/beta controls; EW and value-weighted (WLS) variants.
- `multiple_testing.py` → Harvey–Liu–Zhu *t*>3, Bonferroni, Deflated Sharpe.
- `transaction_costs.py` → turnover + after-cost alpha at 10/25/50 bps.
- `industry_neutral.py` → FF49 industry-neutral alpha.
- `llm_chain.py` → runs the *whole* chain on a candidate JSON.
- `run_all.py` → one-shot orchestrator → `results/final/` + summary + README.
- `factor_report.py` → per-factor bundle (chart + JSON + economic-derivation tree
  + formula tree).
- `ledger_report.py` → the candidate **survival funnel** + structure/family
  breakdown.

---

## Data

| Product | Source (WRDS) |
|---|---|
| Membership + daily OHLCV | CRSP `S&P 500 Index Constituents` (with `MbrStartDt`/`MbrEndDt`) |
| ~160 characteristics | Kelly `Factor_153` panel (1925–2025); 120 usable on S&P 500 member-months at ≤10% missing |
| Risk factors | CRSP / Fama–French "5 Factors + Momentum — Monthly" |

Per-factor missingness is audited in `data/kelly153_coverage.csv`. The coverage
audit **caught and excluded `ret_exc_lead1m`, a forward (next-month) return** that
would have injected look-ahead into the factor pool. Raw WRDS files are **not**
redistributed here — you need your own WRDS access to rebuild the panels.

---

## Quickstart

```bash
# Environment (Python 3.10): QuantaAlpha grammar/parser + statsmodels + deps
conda activate llm-factor

# (one-time) rebuild the panels from WRDS source files
python adapter/build_sp500_membership.py
python adapter/build_sp500_monthly_full.py
python adapter/build_sp500_monthly_kelly.py     # -> data/sp500_monthly_kelly.parquet (default)

# evaluate a single factor
python adapter/evaluate_ic.py '$ret_12_1'
```

```python
from sp500_loader import available_fields, compute_factor
from evaluate_ic   import summary

available_fields()   # the authoritative $-field pool (== GP leaf pool)
summary("RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1)")
#  -> {'IC':..., 'ICIR':..., 'IC_t':..., 'LS_SR':..., ...}
```

Run the full evaluation chain / formal deliverable:

```bash
python adapter/run_all.py --full-trials 300     # -> results/final/
python adapter/llm_chain.py --from-json results/llm_20_valid/...   # gate→...→Fama-MacBeth
```

> **PowerShell note:** quote `$`-expressions with single quotes so the shell does
> not expand them: `python adapter\evaluate_ic.py '$ret_12_1'`.

To run live LLM mining, provide credentials in `QuantaAlpha/.env`
(`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `CHAT_MODEL` / `REASONING_MODEL`). The
loop reuses QuantaAlpha's `openai` client and works with any OpenAI-compatible
endpoint (an Anthropic Claude example is in `QuantaAlpha/.env.claude.example`).

---

## Method note: reusing QuantaAlpha without qlib

QuantaAlpha's operator library (`function_lib.py`) and parser (`expr_parser.py`)
are pure pandas/numpy — the only qlib coupling is the data loader. The panel uses
a MultiIndex `(datetime, instrument)`: cross-sectional operators (`RANK`,
`ZSCORE`, …) group by `datetime`; time-series operators (`TS_*`, `DELAY`, …)
group by `instrument`; at monthly frequency all window units are months. Swapping
in `sp500_loader.py` decouples the whole grammar from qlib.

---

## Status & roadmap

- ✅ Data base, adapter, and full asset-pricing evaluation suite complete.
- ✅ Formal run + robustness (spanning zoo, transaction costs, industry-neutral)
  in `results/formal/`; horse race reconfirmed on the expanded 124-field pool.
- ⏳ Toward submission: multi-model LLM pool (primary + 2 robustness models,
  300-candidate budget), budget-matched GP baseline, q-factor / DHS benchmarks
  + GRS test, Deflated Sharpe with the full candidate-SR distribution, and a
  training-data contamination (look-ahead) audit on the *formulaic* factors.

---

## Related work

AlphaAgent (KDD 2025), Alpha-GPT / Alpha-GPT 2.0, Chain-of-Alpha, FactorMAD,
and the FITEE 2025 survey on LLM-based alpha mining; mechanical baselines
AlphaGen (RL) and AlphaForge; paradigm ancestors FunSearch / AlphaEvolve. This
project's distinguishing angle is asset-pricing rigor + a US-monthly large-cap
setting + an auditable discovery protocol, rather than CS-conference IC/ICIR
backtest metrics on China/daily/qlib data.

---

## Disclaimer

Research code for an academic thesis. Not investment advice. WRDS/CRSP/Compustat
data are licensed and are not included in this repository.

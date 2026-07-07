# Changelog

All notable changes to the LLM-Factor research pipeline. Dates are the working dates.

## 2026-07-07 — Formal run, better spanning zoo, robustness suite, Claude wiring

### Spanning zoo redesigned
- Replaced the 12 arbitrary single-char controls with a **14 JKP-theme composite zoo**
  (value/momentum/reversals/profitability/profit-growth/investment/accruals/issuance/
  quality/low-risk/liquidity/seasonality/mispricing) in `adapter/spanning.py`. Covers the
  whole anomaly space with interpretable, non-multicollinear regressors. It is a harder
  test: under it only `persistent_mispricing_disc` beats the zoo in both windows; others
  become marginal or spanned.

### Robustness modules added
- `adapter/fama_macbeth.py`: value-weighted (WLS, market-cap) Fama-MacBeth alongside EW —
  survivor VW t≈4.9–5.8 (not just small-name effects).
- `adapter/transaction_costs.py`: turnover + after-cost VW long-short alpha at 10/25/50 bps.
  Survivors keep t>2 at 25bps; `persistent_mispricing_disc` lowest turnover (244%/yr), most
  cost-robust (net@50bps t=2.94).
- `adapter/industry_neutral.py`: FF49 industry-neutral alpha (streams `ff49` from the zip ->
  `data/sp500_industry.parquet`, no panel rebuild). Reveals `persistent_mispricing_disc` is
  largely an INDUSTRY bet (OOS 2.62 -> -0.29) while `cash_prof_accrual_quality` /
  `earnings_yield_stability` survive neutralization.

### Claude API wired
- run_sp500 uses QuantaAlpha's `openai` client (installed in the llm-factor env) via
  Anthropic's OpenAI-compatible endpoint — no code change, just `.env`. Added
  `QuantaAlpha/.env.claude.example` and a clear error message. (User must paste their key.)

### Formal run on the 120-factor pool -> results/formal/
- **Horse race (LLM vs full-grammar GP on the 124-field pool):** GP WINS in-sample
  (sel IC 0.0493 > LLM 0.0391, reached LLM level in 180 evals) but its winner
  (`-RANK($inv_gr1a*($dolvol_126d+$ocf_at_chg1)) + RANK($seas_2_5an) + RANK($ret_12_1)`,
  uninterpretable) COLLAPSES OOS (IC 0.0065) and FAILS the gate (OOS t=1.21); the 5 LLM
  survivors PASS (OOS IC 0.014-0.023). Central figure: `horse_race_scatter.png`.
- `results/formal/`: horse_race/, survivors_chain/ (gate, 14-theme spanning, walk-forward,
  multiple-testing, Fama-MacBeth EW+VW), transaction_costs/, industry_neutral/,
  survivors_multilens.csv, README.md. No single factor wins every lens (the honest result).
- Cleared caches (__pycache__, scratchpad); archived raw chain runs to
  `results/archive/2026-07-07_raw_chains/`.


## 2026-07-06 — Fair LLM-vs-GP prompt, Kelly-153 expansion, 1972 window

### Factor universe expanded: curated 38 → 120 usable Kelly-153 characteristics
- Recomputed per-factor missingness for **all Kelly-153 factors** on S&P 500
  member-months over **1972–2025** (the old `data/kelly153_coverage.csv` was broken:
  `miss_pct` exceeded 100%). New coverage script logic lives in the audit; the CSV is
  now annotated with `is_characteristic`, `usable_5pct`, `usable_10pct`,
  `miss_pct_all_member`, `miss_pct_covered`.
- Excluded 13 non-characteristic columns (identifiers `permno/permco/gvkey`, raw
  prices/size `me/prc/dolvol/...`, and returns) — leaving exactly **153 genuine
  characteristics** (self-validating). **Critically caught and excluded
  `ret_exc_lead1m`, a forward (next-month) return** that would have injected
  look-ahead into the factor pool.
- Usable counts (miss ≤ threshold on member-months, 1972–2025):
  ≤5% → 83, **≤10% → 119**, ≤20% → 144. Chose **≤10%**.
- Final set = the 119 usable ∪ the currently-used curated (adds back `noa_at`, just
  over 10%, for continuity) = **120 characteristics**, saved to
  `configs/kelly_usable_factors.json` (new single source of truth).
- Kelly data verified to extend cleanly to 2025 (165/166 columns populated in
  2022–2025; no 2021 cliff).
- **Rebuilt** `data/sp500_monthly_kelly.parquet`: 366,497 rows, **128 $-features
  (8 price/volume + 120 Kelly chars)**, 1965–2025, median char missing 3.0%.
- `adapter/build_sp500_monthly_kelly.py` now reads the usable list from config and
  extracts the Kelly parquet from the zip on demand (new `kelly153_zip` path; `kelly153`
  repointed to a project cache `data/cache/`).

### LLM vs GP made a fair comparison
- **Field pool aligned**: the LLM authoritative field list is now
  `grammar.leaf_fields` — the *identical* pool GP samples leaves from. Expanded
  `fast_full` and `full_llm` `leaf_fields` to the new **124-field pool** (4 price/volume
  cores `$close $volume $me $return` + 120 Kelly chars). Verified LLM pool == GP pool.
- Both sides share the same operators (`fast_full`) and windows `[3,6,12,24,36]`.

### Discovery-prompt policy frozen (no example factors)
- Removed all worked/example factor expressions and all in-sample IC numbers from the
  prompt. The discovery prompt now contains exactly three parts: **data/rules
  description + field list + operator glossary** — matching QuantaAlpha's own prompt
  form (operator glossary + rules, no full factors). Standing rule documented in
  `PROJECT_STATE.md` and as an editor note in `adapter/scenario_sp500.md`.
- `build_scenario()` strips HTML comments so the editor note never reaches the LLM.
- Expression syntax is unchanged QuantaAlpha/AlphaAgent grammar (`$field` + `RANK/TS_*`
  + infix `+ - * /`, parsed by QuantaAlpha's own `expr_parser`/`function_lib`).

### All analysis windows start 1972-01
- Unified the sample start from `1972-07-01` → **`1972-01-01`** across config and all
  adapter scripts (13 files). The OOS split stays `2000-12-31`; walk-forward first-OOS
  stays `1990-01-01` (a separate design choice, needs pre-1990 training).
- The panel retains 1965–1972 **price/volume rows only as time-series warmup** for
  `TS_*` operators; no analysis uses them (every eval filters to the start date).

### Field dictionary injected into the prompt
- New `configs/factor_dictionary.json` — a one-line economic definition for every pool
  field (120 JKP/Kelly abbreviations + 4 price/volume cores), curated from standard
  JKP / Chen-Zimmermann definitions (swap in the official JKP "Factor Details" text if
  available). `build_scenario()` now emits a **FIELD DICTIONARY** section so the LLM can
  reason economically about cryptic names (`$cop_atl1`, `$nfna_gr1a`, ...). Verified all
  124 pool fields have a definition. This is field-list metadata, not example factors, so
  it complies with the discovery-prompt policy.

### Per-factor report bundles
- New `adapter/factor_report.py` — for each factor writes one folder
  `results/factor_reports/<factor>/` with `<factor>.png` (4-panel chart), `<factor>.json`,
  `trees/<factor>.{md,png}` (economic derivation tree), and
  `formula_trees/<factor>.{md,png}` (GP-style formula tree), plus top-level `index.md`,
  `summary.csv`, `MANIFEST.json`. Run: `python adapter/factor_report.py --set thesis_extended`
  or `--factors <names>`. Tested on `mispricing_combo` (PASS, VW FF5+UMD t=4.08/OOS 2.96)
  and `mispr_fin_quality` (PASS, t=3.63/OOS 2.75) on the new 1972-2025 panel.

### LLM-generated factors run through the full chain (Claude as the LLM)
- New `adapter/llm_chain.py` — runs the whole evaluation chain (gate → spanning →
  walk-forward → HLZ multiple-testing → Fama-MacBeth) on LLM candidates; `factor_report.py`
  gained `--from-json`.
- Acting as the LLM on the expanded pool + dictionary, generated 10 economically-grounded
  candidates using **new** characteristics (cash profitability, accruals, PEAD surprises,
  equity duration, MAX/lottery, Altman-Z, QMJ, net payout). Funnel: **10 → 4 gate-pass →
  3 full-chain survivors**. `ev_value_cash_profitability` had the highest OOS gate alpha
  (t=3.37) but is **spanned by the anomaly zoo** — dropped by the chain (the chain does real
  work beyond the gate).
- Survivors (beat gate + zoo-spanning + walk-forward + HLZ t>3 + Fama-MacBeth), all built on
  newly-available fields: `cash_prof_accrual_quality`, `quality_bloat_value`,
  `shareholder_yield_quality`. Full deliverable in `results/llm_factors_final/` (per-factor
  chart + json + derivation/formula trees, chain tables, SUMMARY.png, README, survivors_summary.csv).

### Interaction batch (structure test)
- Ran a second LLM batch of 10 candidates deliberately using `*`, `/`, `TS_*` through the
  same chain (`chain_interactions/`). Result: pure multiplicative `ZSCORE*ZSCORE`
  interactions (0/3 gate) consistently die (monotonicity breaks, OOS≈0), but a **ratio**
  (`earnings_yield_stability`) and a **time-series** (`persistent_mispricing_disc`) survive
  the full chain. Combined valid set = **5 factors** (3 rank-sum + 1 ratio + 1 TS) in
  `results/llm_factors_final/` — the survivors are NOT all additive; the failure is specific
  to multiplicative interactions.

### Results cleanup
- Archived superseded exploratory result folders (manual_llm_*, horserace_full_*, extended_*)
  to `results/archive/2026-07-07_preexpansion/`; removed transient test dirs and the 7.7 GB
  scratchpad Kelly extract (regenerable from the zip). Kept `final/`, `candidate_ledgers/`,
  `llm_chain/`, `llm_factors_final/`.

### New / changed files
- New: `adapter/ledger_report.py` — candidate **survival funnel** + structure/family
  breakdown from the strict-mining ledger → `candidate_distribution.md`.
- New: `configs/kelly_usable_factors.json`, config paths `kelly153_zip` /
  `kelly_usable_factors`; `kelly153` repointed to project cache.
- Changed: `configs/llm_factor.json` (paths, `sample.start`, grammar `leaf_fields`),
  `adapter/scenario_sp500.md`, `adapter/run_sp500.py`, `adapter/build_sp500_monthly_kelly.py`,
  `data/sp500_monthly_kelly.parquet`, `data/kelly153_coverage.csv`, `PROJECT_STATE.md`.

### Empirical note (strict-mining survival funnel, pre-expansion run)
- Of full-sample-significant economic composites, only ~43% survive OOS (median full VW
  FF5+UMD t≈3.4, OOS t≈1.85; ~57% below 1.96). Additive rank-sums survive; multiplicative
  interactions and ratios mostly die. Gate-PASS saturates at a few mutually-uncorrelated
  survivors (all one mispricing/financing-discipline mechanism) — the distribution, not a
  winner count, is the deliverable.

# Scenario: S&P 500 monthly multi-factor mining

This text is injected into the LLM prompt so generated factors are computable on
our data. (The live field list + operators are appended automatically by
`run_sp500.py` from `available_fields()`.)

<!-- STANDING RULE (see PROJECT_STATE.md "LLM discovery prompt policy"):
     This prompt contains ONLY three things - data/rules description, field list,
     and operator glossary. Do NOT add any worked/example factor expression
     (e.g. `RANK($x) - RANK($y)`) and do NOT report in-sample performance
     (no "IC t≈…"). Placeholder operator snippets like `TS_MEAN(A, 12)` are fine. -->


## Market & data
- **Universe**: U.S. equities, **point-in-time S&P 500 constituents** (~500 names/month, survivorship-bias-free).
- **Frequency**: **monthly** (month-end observations). All rolling windows are in **months** (e.g. `TS_MEAN(A, 12)` = trailing 12 *months*).
- **Panel**: cross-section of ~500 stocks per month, ~1965-2025.
- **Target / label**: next-month excess return. A good factor has high cross-sectional **RankIC** vs this label.

## Rules for factor expressions
1. Use **only** the `$`-fields listed below and the operators listed below. Do not invent field names.
2. Each factor is **one expression** producing a per-(month, stock) value. It will be cross-sectionally ranked each month, then correlated with next-month return.
3. Prefer **cross-sectionally comparable** constructs - wrap level/size-dependent terms in `RANK(...)` or `ZSCORE(...)`.
4. No look-ahead: only use contemporaneous fields (the label is already forward).
5. Combine **different data types** (e.g. value x quality x risk) - multi-category factors tend to score best here.
6. Keep it parsimonious (<= ~5 base fields); avoid trivial restatements of a single field.

## Field categories (price/volume + Kelly-153 characteristics)
These categories are illustrative; the binding pool is the AUTHORITATIVE FIELD LIST
appended below (identical to the GP leaf pool, for a fair LLM-vs-GP comparison).
- **price/volume/size**: `$close $volume $me $return`
- **momentum**: `$ret_1_0 $ret_6_1 $ret_12_1 $ret_12_7 $resff3_12_1`
- **value**: `$be_me $at_me $ni_me $sale_me $bev_mev $eqnpo_12m`
- **quality/profitability**: `$gp_at $op_at $ni_be $at_turnover $qmj_prof`
- **investment/growth**: `$at_gr1 $sale_gr1 $noa_at $chcsho_12m`
- **issuance**: `$eqnetis_at $dbnetis_at`
- **distress/safety**: `$qmj_safety $z_score`
- **risk/volatility**: `$beta_60m $ivol_ff3_21d $rmax5_21d $betadown_252d $rvol_21d`
- **liquidity**: `$turnover_126d $ami_126d $dolvol_126d $bidaskhl_21d $prc_highprc_252d`
- **seasonality**: `$seas_1_1na` · **mispricing**: `$mispricing_perf $mispricing_mgmt`

## Operators
The authoritative operator grammar is appended automatically by `run_sp500.py`.
Use only the operators in that appended `PRIMARY OPERATOR GRAMMAR`; do not use
operators merely because they appear in older QuantaAlpha examples.

## Expression form
Write each factor as ONE expression in the QuantaAlpha / AlphaAgent grammar: `$fields`
from the authoritative list combined with the operators defined in the appended
PRIMARY OPERATOR GRAMMAR (arithmetic `+ - * /`, cross-sectional `RANK/ZSCORE/SCALE`,
and the listed `TS_*` transforms). Use a balanced mix of additive, multiplicative,
ratio, and time-series structures. No worked example factors are provided - propose
from economic reasoning, not from a template.

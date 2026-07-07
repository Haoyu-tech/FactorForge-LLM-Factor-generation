# Top-Tier Empirical Research Design

This document defines the submission-grade empirical design for the LLM-Factor
paper. The current 20-factor extended pool is a pilot evidence set. The final
paper should scale the design to a pre-specified, auditable discovery pool with
a budget-matched GP baseline.

## 1. Research Question

The empirical question is:

> Can LLMs generate economically interpretable equity factors that survive
> modern asset-pricing validation better than budget-matched GP search?

The LLM is not treated as a return-forecasting black box. It is treated as a
structured economic hypothesis generator. A valid hypothesis contains:

| Component | Requirement |
|---|---|
| Name | Stable factor identifier |
| Expression | Grammar-valid formula over approved fields |
| Rationale | Economic mechanism written before OOS evaluation |
| Provenance | Model, prompt version, timestamp, and candidate status |

## 2. Candidate Generation Design

### 2.1 LLM Pool

Use three LLMs, each with the same prompt family, grammar, field list, and
candidate budget.

| Generator | Candidate budget | Purpose |
|---|---:|---|
| Primary LLM | 100 | Main discovery model |
| Robustness LLM 1 | 100 | Model-level robustness |
| Robustness LLM 2 | 100 | Model-level robustness |
| Total LLM pool | 300 | Main LLM discovery pool |

Every attempted candidate is logged. Failed candidates remain in the ledger.

### 2.2 Baseline Pool

The main baseline is full-grammar genetic programming (GP). It is stronger and
more relevant than random expression search because it actively optimizes over
the same expression language. Random grammar search can remain an appendix
diagnostic, but it is not part of the main empirical design.

| Baseline | Candidate budget | Purpose |
|---|---:|---|
| GP full-grammar search | 300 | Strong symbolic-search benchmark |
| Random grammar search | Optional appendix only | Null diagnostic, not a main baseline |

The LLM and GP search use:

| Shared Condition | Rule |
|---|---|
| Parser | Same expression parser |
| Grammar | Same `fast_full` grammar |
| Field list | Same approved data fields |
| Candidate accounting | Same ledger rules |
| Selection windows | Same discovery and validation windows |
| Final testing | Same locked OOS evaluation |

## 3. Sample Split

For a top-tier design with hundreds of candidates, use three sample windows.

| Window | Dates | Use |
|---|---|---|
| Discovery | 1972-07-01 to 1994-12-31 | Score generated candidates and remove weak candidates |
| Validation | 1995-01-01 to 2000-12-31 | Select final factors and factor families |
| Locked OOS | 2001-01-01 to sample end | Final test only, never used for selection |

The current 1972-2000 / post-2000 split remains useful for pilot evidence. The
submission-grade design should use the three-window split because a 300-factor
candidate pool creates more data-snooping pressure.

## 4. Candidate Funnel

The paper should report the full funnel rather than only the winners.

| Stage | Rule | Output |
|---|---|---|
| Attempted | All generated expressions | 300 LLM + 300 GP |
| Parseable | Expression parses under grammar | Candidate count by method |
| Covered | Coverage >= 80% in discovery sample | Candidate count by method |
| Non-duplicate | Not same expression and not near-identical family | Candidate count by method |
| Economically valid | Non-empty rationale for LLM candidates | Candidate count by LLM |
| Discovery screen | Discovery IC > 0 and IC_t above pre-set threshold | Shortlist |
| Validation screen | Validation IC same sign and VW FF5+UMD alpha not weak | Final selected factors |
| Locked OOS | No further selection | Report final performance |

Recommended thresholds:

| Screen | Rule |
|---|---|
| Coverage | >= 80% |
| Discovery IC | positive |
| Discovery IC_t | >= 2.0 for shortlist |
| Validation IC | same sign as discovery |
| Validation alpha | VW FF5+UMD alpha t >= 1.5 for final shortlist |
| Headline factor | Full-sample t > 3 and locked OOS t >= 2 preferred |

The exact thresholds should be declared before the final 300-candidate run.

## 5. Factor Family Clustering

Hundreds of LLM candidates will produce similar signals. The paper should report
factor families, not just isolated expressions.

### 5.1 Correlation Clustering

Compute monthly value-weighted long-short returns for all valid candidates in
the discovery window. Cluster candidates using return correlations.

| Rule | Interpretation |
|---|---|
| Correlation >= 0.90 | Same factor family |
| Correlation 0.70-0.90 | Related family, report separately if economics differ |
| Correlation < 0.70 | Distinct factor family |

Within each family, select a representative using:

1. Simpler expression.
2. Stronger validation IC.
3. Stronger validation VW FF5+UMD alpha.
4. Clearer economic rationale.

This prevents the paper from over-counting many variants of the same economic
idea.

### 5.2 Expected Families

The current 20-factor pilot suggests likely families:

| Family | Examples |
|---|---|
| Mispricing composite | `mispricing_combo`, `liquid_mispricing` |
| Mispricing + financing discipline | `mispr_fin_disc`, `mispr_fin_quality` |
| Financing + reversal/momentum | `financing_reversal_guard`, `issuance_trend_reversal` |
| Quality/value/investment discipline | `investment_quality_ratio`, `cheap_prof_lowissue` |
| Risk-adjusted momentum/discipline | `risk_adjusted_fin_disc`, `value_mom_stability` |

## 6. Portfolio-Level Tests

For every selected factor and every method-level winner:

| Test | Specification |
|---|---|
| Sort | Monthly decile sort |
| Long-short | D10 minus D1 |
| Main weighting | Value-weighted by market equity |
| Supplementary weighting | Equal-weighted |
| Rebalancing | Monthly |
| Main alpha | FF5+UMD alpha |
| Standard errors | Newey-West, 6 lags |

Main portfolio outputs:

| Metric | Report |
|---|---|
| Annualized long-short return | Full, validation, OOS |
| Sharpe ratio | Full, validation, OOS |
| FF5+UMD alpha | Annualized alpha and t-stat |
| Decile monotonicity | Spearman correlation across deciles |
| Turnover | Monthly one-way turnover |
| Transaction-cost alpha | Alpha after cost assumptions |

## 7. Cross-Sectional Tests

Use Fama-MacBeth regressions to show that the factor is not merely a portfolio
construction artifact.

Monthly regression:

```text
r_{i,t+1} = gamma_0,t + gamma_1,t factor_{i,t}
          + controls_{i,t} + epsilon_{i,t+1}
```

Controls:

| Control | Variable |
|---|---|
| Size | log market equity |
| Value | book-to-market |
| Momentum | prior 12-1 return |
| Market beta | 60-month beta |
| Optional | idiosyncratic volatility, profitability, investment |

Report:

| Metric | Meaning |
|---|---|
| Univariate slope | Raw cross-sectional predictability |
| Multivariate slope | Increment after controls |
| Newey-West t | Time-series t-stat of monthly slopes |
| Average R2 | Cross-sectional explanatory power |

## 8. Spanning and Incremental Value

Run two spanning tests for each selected factor:

| Test | RHS factors | Question |
|---|---|---|
| Component spanning | Univariate long-short portfolios of the factor's own fields | Does the combination add value beyond ingredients? |
| Anomaly-zoo spanning | Kelly-style canonical anomaly set | Does it add value beyond known anomalies? |

Regression:

```text
LS_factor,t = alpha + beta' LS_spanning_set,t + epsilon_t
```

Report annualized intercept and Newey-West t-stat.

## 9. Multiple Testing and False Discovery Control

With 300 LLM candidates, multiple-testing treatment is central.

Report at least:

| Adjustment | Purpose |
|---|---|
| HLZ t > 3 | Conservative new-factor threshold |
| Bonferroni | Family-wise error control using attempted candidate count |
| Benjamini-Hochberg FDR | False discovery rate across the candidate pool |
| Deflated Sharpe Ratio | Sharpe adjusted for non-normality and number of trials |
| Bootstrap reality check | Optional but strongest |

Candidate budget must be the number of attempted candidates, not only valid or
selected candidates. For the full design:

| Pool | N for multiple testing |
|---|---:|
| Primary LLM only | 100 |
| All LLMs | 300 |
| GP baseline | 300 |
| All generated candidates | 600, for global robustness appendix |

## 10. Method-Level Comparison

The AI contribution should be evaluated at the method level, not only through
the best factor.

Main method comparison table:

| Method | Attempts | Valid | Unique families | Selected | OOS pass | Best OOS t | Avg OOS IC |
|---|---:|---:|---:|---:|---:|---:|---:|
| LLM primary | 100 |  |  |  |  |  |  |
| LLM robustness 1 | 100 |  |  |  |  |  |  |
| LLM robustness 2 | 100 |  |  |  |  |  |  |
| All LLMs | 300 |  |  |  |  |  |  |
| GP full grammar | 300 |  |  |  |  |  |  |

The headline claim should be:

> LLM-generated candidates produce more economically interpretable selected
> factors and stronger locked-OOS survival than budget-matched full-grammar GP
> search.

## 11. Robustness Checklist

Required before submission:

| Robustness | Purpose |
|---|---|
| Three LLMs | Model-level robustness |
| GP full-grammar baseline | Strong symbolic-search benchmark |
| Random grammar baseline | Optional appendix diagnostic |
| Factor-family clustering | Avoid over-counting variants |
| Turnover and transaction costs | Implementability |
| Liquidity filters | Avoid illiquid anomaly concern |
| Mega-cap subsample | Large-cap robustness |
| Subperiods | Stability across regimes |
| Excluding micro periods | Avoid crisis-specific dependence |
| Alternative alpha models | FF3, Carhart4, FF5, FF5+UMD |

## 12. Paper Tables

Recommended empirical tables:

| Table | Title | Content |
|---|---|---|
| 1 | Candidate Funnel | Attempts, valid, unique, selected, OOS pass by method |
| 2 | Selected LLM Factors | Name, expression class, rationale family, source model |
| 3 | Main Portfolio Results | VW FF5+UMD alpha, full/validation/OOS |
| 4 | Multiple Testing | HLZ, Bonferroni, FDR, DSR |
| 5 | LLM vs GP Baseline | Method-level comparison |
| 6 | Fama-MacBeth | Firm-level slopes with controls |
| 7 | Spanning Tests | Increment beyond components and anomaly zoo |
| 8 | Trading Costs | Turnover and cost-adjusted alpha |

Appendix:

| Appendix Table | Content |
|---|---|
| A1 | Full candidate ledger summary |
| A2 | All generated expressions and statuses |
| A3 | Factor family correlation clusters |
| A4 | Equal-weighted results |
| A5 | Alternative sample splits |

## 13. Current Pilot Evidence

The current repository already contains a pilot version of this design:

| Item | Current status |
|---|---|
| LLM candidates | 20 in `thesis_extended` |
| Factor-lab pass | 6 of 20 |
| Full-sample HLZ pass | 12 of 20 |
| DSR > 0.95 | 3 of 20 |
| GP baseline | Available, needs budget-matched refresh |
| Three-LLM design | Not yet run |

The pilot evidence is useful for drafting and debugging. The submission version
should scale the same protocol to the 300-candidate LLM pool and a
budget-matched 300-candidate GP baseline.

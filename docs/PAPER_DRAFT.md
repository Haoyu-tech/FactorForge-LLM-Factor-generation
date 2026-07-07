# Economic Hypothesis Generation with Large Language Models:
# Evidence from Equity Factor Discovery

## Abstract

Large language models (LLMs) are increasingly used to assist scientific
discovery, but their role in empirical asset pricing remains unclear. The main
concern is not whether an LLM can propose a profitable-looking signal; a flexible
model can generate many candidates, and standard return predictability tests are
especially vulnerable to data mining. This paper studies a narrower and more
auditable question: can LLMs generate economically interpretable stock-return
factors that survive pre-specified empirical asset-pricing validation?

We build an LLM-guided factor discovery pipeline on a monthly S&P 500 panel from
1972 to 2025. The LLM proposes grammar-valid factor expressions using price,
size, profitability, value, investment, issuance, risk, liquidity, and
mispricing characteristics. Each proposal must include an economic rationale
before out-of-sample evaluation. Candidate generation is separated from
validation through an append-only ledger, a fixed discovery/OOS split, and a
common parser shared by LLMs and mechanical-search baselines. Final factors are
tested using value-weighted long-short portfolios, Fama-French five-factor plus
momentum alphas, walk-forward evaluation, spanning regressions, Fama-MacBeth
cross-sectional regressions, and multiple-testing haircuts.

We evaluate an expanded pool of 20 economically motivated LLM-generated
candidate factors. Six survive the full+OOS factor-lab gate. Four are especially
strong headline candidates because they combine full-sample FF5+UMD alpha
significance above conventional new-factor thresholds with OOS survival:
`financing_reversal_guard`, `mispricing_combo`, `mispr_fin_quality`, and
`mispr_fin_disc`. For example, `mispricing_combo` earns an annualized
value-weighted FF5+UMD alpha of 8.9% in the full sample with a Newey-West
t-statistic of 3.93 and remains significant out of sample with t=2.96.
`mispr_fin_quality` earns a 7.3% annualized FF5+UMD alpha with t=3.50 and OOS
t=2.75, while `mispr_fin_disc` earns a 7.5% alpha with t=3.41 and OOS t=2.31.
A full-grammar genetic-programming baseline does not pass the same OOS
asset-pricing gate. The evidence suggests that LLMs are useful not as black box
return predictors, but as auditable generators of economically structured
hypotheses.

## 1. Introduction

Large language models have changed the cost of generating research hypotheses.
In finance, this change is both promising and dangerous. Asset pricing has a
long tradition of using economic theory, accounting variables, and market data
to construct return predictors. It also has a long tradition of false discovery:
when researchers can try many signals, transformations, and subsamples, some
factors will appear significant by chance. LLMs intensify this problem because
they can rapidly propose many plausible factor definitions. A credible use of
LLMs in empirical asset pricing therefore requires a design that separates
hypothesis generation from performance validation.

This paper asks whether LLMs can serve as disciplined economic hypothesis
generators for equity factor discovery. The question is intentionally narrower
than whether an LLM can "beat the market." We do not use the LLM as a black-box
forecasting model, and we do not allow it to optimize on out-of-sample returns.
Instead, the LLM proposes interpretable factor expressions over a fixed grammar
and a fixed set of stock characteristics. Each proposed factor must have an
economic rationale before validation. The factors are then passed through a
standard empirical asset-pricing pipeline that is independent of the LLM.

The core design principle is auditability. Every generated candidate is recorded
in an append-only ledger, including invalid expressions, duplicates, missing
rationales, and failed factors. The discovery sample is fixed from July 1972
through December 2000. The post-2000 sample is held out for validation. The LLM
is not shown OOS performance during generation, prompt revision, or candidate
selection. The same expression parser and operator grammar are used for LLM
factors and for mechanical-search baselines. This structure turns the LLM from
an unconstrained search device into a documented source of economic hypotheses.

We apply the framework to a monthly S&P 500 panel covering 1972 to 2025. The
candidate factor language combines price and volume variables with a broad set
of accounting and anomaly characteristics, including profitability, value,
investment, issuance, risk, liquidity, and the Stambaugh-Yuan mispricing
measures. The main validation target is value-weighted long-short performance,
which is more demanding than equal-weighted performance and better reflects the
large-cap investment universe. Risk adjustment uses the Fama-French five-factor
model augmented with momentum (FF5+UMD). We also report out-of-sample alphas,
walk-forward stability, spanning regressions against both component factors and
a Kelly anomaly zoo, firm-level Fama-MacBeth regressions, and multiple-testing
adjustments.

The main result is that the LLM produces a broad but selective discovery pool.
Among 20 economically motivated candidates, six survive the full+OOS
factor-lab gate. The strongest validated signals include `financing_reversal_guard`,
which combines low equity and debt issuance with momentum and a short-term
reversal guard; `mispricing_combo`, which combines the performance and
management mispricing composites; `mispr_fin_quality`, which adds profitability
support to the mispricing-financing discipline mechanism; and `mispr_fin_disc`,
which links behavioral mispricing to low equity issuance and low asset growth.
These factors earn annualized value-weighted FF5+UMD alphas between 7.3% and
11.7% in the full sample and remain significant out of sample.

The results also show why the audit trail matters. Not every plausible
LLM-generated factor survives. A quality-value-momentum combination has strong
full-sample performance but fails the strict OOS gate. A pure
financing-investment discipline factor has significant cross-sectional
predictability but weak OOS value-weighted alpha. These failures are not swept
away; they are part of the evidence. The paper therefore evaluates the LLM as a
process for generating testable economic hypotheses, not as an oracle that only
produces winners.

We compare the LLM-generated factors with a full-grammar genetic-programming
baseline that searches the same expression language using the same evaluation
engine. The mechanical-search winner attains competitive in-sample selection
performance but does not pass the OOS value-weighted FF5+UMD alpha gate. This
contrast is important. If the LLM merely performed unconstrained symbolic search,
then a grammar-matched search procedure should perform similarly. The evidence
instead points to a more specific advantage: LLMs help combine economically
meaningful characteristics into interpretable hypotheses that are simple enough
to test and robust enough to survive validation.

This paper contributes to three literatures. First, it contributes to empirical
asset pricing by proposing and validating economically interpretable composite
factors built from mispricing, financing, and investment discipline. Second, it
contributes to the literature on data mining and multiple testing in factor
research by showing how LLM-generated hypotheses can be made auditable through
fixed splits, ledgers, grammars, and budget accounting. Third, it contributes to
the emerging literature on LLMs for scientific discovery by shifting the role of
LLMs from black-box prediction to structured hypothesis generation.

The central message is deliberately modest. LLMs do not replace asset-pricing
theory, econometric validation, or out-of-sample testing. Their value is in
compressing economic knowledge into candidate hypotheses that can be evaluated
by conventional empirical standards. In this setting, the useful object is not
the model's text output by itself, but the auditable loop connecting a
pre-specified prompt, a grammar-valid factor expression, an economic rationale,
a candidate ledger, and a locked validation sample.

## 2. Conceptual Framework

### 2.1 LLMs as Hypothesis Generators

The pipeline treats an LLM as a generator of structured economic hypotheses. A
hypothesis consists of three components: a factor expression, a factor name, and
an economic rationale. The factor expression must be computable on the monthly
panel using the approved operator grammar. The rationale must explain why the
signal should predict future returns in asset-pricing terms, such as
mispricing, limits to arbitrage, investment discipline, financing behavior,
quality, risk, or investor underreaction.

This design differs from a direct machine-learning return prediction exercise.
The LLM does not observe firm-level future returns, does not estimate portfolio
weights, and does not update parameters month by month. Its output is a static,
interpretable characteristic that can be tested like a traditional factor. This
keeps the empirical object close to standard asset-pricing research and makes it
possible to compare LLM-generated signals with known anomalies and mechanical
symbolic search.

### 2.2 Why Auditability Is Necessary

An unconstrained LLM factor-mining exercise would be difficult to interpret.
Given enough prompts, model choices, candidate expressions, and researcher
iterations, a significant factor may emerge by chance. The paper therefore
pre-specifies the discovery protocol. Candidate generation occurs before OOS
evaluation. All attempts are recorded. Invalid and failed factors remain in the
ledger. The total candidate budget is used in multiple-testing adjustments.

The audit structure is designed to address three common objections:

1. **Data-snooping concern:** the LLM may generate many candidates and retain
   only the best. We address this with candidate-budget accounting,
   Harvey-Liu-Zhu style t-stat thresholds, Bonferroni adjustments, and Deflated
   Sharpe Ratios.
2. **OOS leakage concern:** researchers may revise prompts after seeing OOS
   results. We address this by fixing the discovery/OOS split and treating OOS
   results as locked validation.
3. **Search-equivalence concern:** the LLM may simply be doing symbolic search.
   We address this with grammar-matched mechanical baselines.

### 2.3 Economic Interpretability

A factor is useful for this paper only if it is both computable and economically
interpretable. Interpretability does not mean the factor must be new in every
component. Many established factors are combinations of known characteristics.
The question is whether the LLM can produce combinations that have a coherent
economic mechanism and survive validation beyond their ingredients.

For example, `mispricing_combo` combines two broad mispricing composites. The
economic rationale is that the two measures aggregate different behavioral
anomalies and capture persistent overpricing or underpricing not fully explained
by standard risk models. The factor `mispr_fin_disc` extends this logic by
penalizing high equity issuance and high asset growth, linking mispricing with
corporate financing and investment discipline. These are not opaque
transformations; they are testable economic claims.

## 3. Data and Factor Language

### 3.1 Data

The empirical universe is the S&P 500 at monthly frequency. Index membership is
constructed using point-in-time constituent information, and stock returns are
aligned with next-month excess returns. The main panel begins in July 1972,
when accounting-based characteristics have broad coverage, and extends through
2025. The primary panel combines price and volume variables with a broad set of
Kelly-style stock characteristics.

The full sample is used for headline statistical power, following standard
empirical asset-pricing practice. The post-December-2000 period is treated as
out-of-sample validation. The discovery sample ends in December 2000 and is the
only period available for candidate selection.

### 3.2 Approved Characteristics

The factor language includes variables from the following categories:

| Category | Examples |
|---|---|
| Momentum and reversal | prior returns, residual momentum, short-term reversal |
| Value | book-to-market, earnings-to-market, sales-to-market |
| Profitability and quality | gross profitability, operating profitability, QMJ profitability |
| Investment and financing | asset growth, net equity issuance, debt issuance |
| Risk | beta, idiosyncratic volatility, downside beta |
| Liquidity | turnover, dollar volume, bid-ask proxy |
| Mispricing | performance and management mispricing composites |
| Size and price-volume | market equity, close price, volume, monthly return |

### 3.3 Operator Grammar

All candidate expressions must be valid under a pre-specified grammar. The main
grammar allows cross-sectional transformations such as `RANK`, `ZSCORE`, and
`SCALE`; time-series transformations such as `TS_MEAN`, `TS_STD`, `TS_ZSCORE`,
`TS_MAX`, `TS_MIN`, `DELTA`, `DELAY`, and `TS_PCTCHANGE`; and arithmetic
operations such as addition, subtraction, multiplication, and division. Window
lengths are fixed at 3, 6, 12, 24, and 36 months. The same grammar is used for
LLM proposals and mechanical-search baselines.

The grammar serves two purposes. First, it prevents the LLM from proposing
uncomputable or open-ended formulas. Second, it creates a fair comparison with
symbolic search methods, because both LLM and baseline candidates must pass
through the same parser and evaluation engine.

## 4. LLM Factor Generation Protocol

### 4.1 Model Roles

The submission-grade design uses one primary LLM and two robustness LLMs. Each
LLM receives the same data dictionary, operator grammar, field list, and
instructions. The primary LLM generates 100 attempted candidates. Each
robustness LLM also generates 100 attempted candidates, producing a 300-factor
LLM discovery pool. The robustness models test whether the results are specific
to one model rather than being used to replace the primary model after OOS
results are known.

For every model run, the ledger records the model name, provider, prompt
version, grammar, candidate budget, valid candidates, failed candidates,
selection metric, and timestamp. This information is reported in the audit
appendix.

The current 20-factor extended pool is treated as a pilot implementation of
this protocol. It is useful for establishing the empirical pipeline and for
showing preliminary evidence, but the submission version should use the full
300-candidate design and a budget-matched GP baseline.

### 4.2 Candidate Generation

The prompt gives the LLM the data dictionary, approved operators, sample split,
and target of generating economically interpretable stock-return factors. The
LLM must return a structured candidate with a name, expression, and rationale.
Candidates are rejected if they are not parseable, reference unavailable fields,
duplicate a previous candidate, have insufficient data, or lack an economic
rationale.

Rejected candidates are not deleted. They remain in the append-only ledger and
count toward the attempted candidate budget where appropriate. This prevents the
reported discovery process from being reduced to a hand-picked set of survivors.

### 4.3 Selection

For the submission-grade design, candidate selection uses a three-window split.
The discovery window runs from July 1972 to December 1994 and is used to score
and screen generated candidates. The validation window runs from January 1995
to December 2000 and is used to select final factors and factor-family
representatives. The post-2000 period is the locked OOS window and is never used
for factor selection.

The primary selection criteria are expression validity, non-empty economic
rationale, sufficient coverage, positive discovery RankIC, validation IC with
the same sign, and validation-period portfolio performance under the
pre-registered ranking rule. No post-2000 return, IC, alpha, or walk-forward
result is used during selection.

After selection, all reported factors are evaluated under the same validation
pipeline. The LLM cannot revise a factor after seeing its OOS performance.

### 4.4 Baseline

The LLM discovery pool is compared with a budget-matched full-grammar genetic
programming baseline. GP performs symbolic search using the same parser,
operator grammar, field list, selection window, and evaluation engine as the
LLM-generated candidates. It receives the same 300-candidate budget as the
combined LLM pool. This design separates the contribution of economic
language-model synthesis from the contribution of mechanical expression search.

Random grammar search is not part of the main empirical design. It can be
reported as an appendix diagnostic, but the main comparison is LLM versus
strong GP search.

## 5. Empirical Validation

### 5.0 Candidate Funnel

The empirical design reports the full candidate funnel. This is central to the
paper because the object of study is a discovery process, not only the final
winners. The funnel records attempted candidates, parseable expressions,
candidates with sufficient coverage, unique factor families, candidates passing
the discovery screen, candidates passing the validation screen, and factors
that survive locked OOS testing.

The preferred funnel is:

```text
attempted candidates
-> parseable expressions
-> sufficient coverage
-> unique factor families
-> positive discovery IC
-> validation-screen survivors
-> locked-OOS results
```

Candidate counts are reported separately for the primary LLM, the two
robustness LLMs, all LLMs combined, and GP search.

### 5.1 Portfolio Tests

Each factor is sorted into deciles each month. The main portfolio test is a
value-weighted long-short return, long the top decile and short the bottom
decile. Equal-weighted returns are reported as supplementary evidence. The
value-weighted test is the headline specification because the S&P 500 is a
large-cap universe and equal-weighted anomalies can be driven by smaller,
less-investable names.

Risk-adjusted performance is measured using nested factor models: CAPM, FF3,
Carhart four-factor, FF5, and FF5+UMD. The primary alpha is the value-weighted
FF5+UMD alpha with Newey-West standard errors.

### 5.2 Out-of-Sample and Walk-Forward Tests

The post-2000 period is the locked OOS validation sample. A factor passes the
strict gate only if it has a non-empty rationale, monotone full-sample decile
returns, value-weighted FF5+UMD alpha significance in both the full sample and
the OOS sample, and consistent IC sign between discovery and OOS periods.

Walk-forward tests divide the OOS period into three-year blocks and report the
mean block IC, the fraction of positive blocks, the block-level t-statistic, and
the worst block. This shows whether a factor's performance is concentrated in a
single period or persists across market regimes.

### 5.3 Spanning Tests

For each factor, we regress its value-weighted long-short return on two
spanning sets. The first set contains the factor's own component characteristics
as univariate long-short portfolios. The second set is a Kelly anomaly zoo
containing canonical momentum, reversal, value, profitability, investment,
issuance, risk, size, and liquidity signals. A significant intercept indicates
that the LLM-generated combination is not fully spanned by its ingredients or
by the broader anomaly library.

### 5.4 Fama-MacBeth Regressions

Portfolio sorts are complemented with firm-level Fama-MacBeth regressions. Each
month, next-month stock returns are regressed on the factor and controls for
size, book-to-market, momentum, and beta. Predictors are cross-sectionally
standardized each month. The reported slope is the average monthly return
associated with a one-standard-deviation increase in the factor, with
Newey-West standard errors over time.

### 5.5 Multiple-Testing Haircuts

Because the paper studies factor generation, raw t-statistics are not enough.
We report the Harvey-Liu-Zhu rule-of-thumb threshold that new factors should
exceed |t|=3.0, Bonferroni-adjusted p-values using the attempted candidate
budget, and Deflated Sharpe Ratios that account for the expected maximum Sharpe
ratio across trials. These adjustments are applied to the candidate-generation
budget, not just to the surviving factors.

In the full submission design, the main multiple-testing budget is 300 for the
combined LLM discovery pool. We also report model-level adjustments using
N=100 for each individual LLM and baseline-level adjustments using N=300 for
GP search. A global appendix can use N=600 for all LLM and GP candidates
combined. This conservative accounting prevents the paper from treating a
large generated pool as if it were a small set of hand-proposed factors.

### 5.6 Factor-Family Clustering

A large LLM candidate pool will contain many near-duplicates. To avoid
over-counting variants of the same economic idea, candidate factors are grouped
into families using the correlation of their discovery-period value-weighted
long-short returns. Candidates with return correlation above 0.90 are treated
as the same family. Within each family, the representative factor is selected
using expression simplicity, validation-period IC, validation-period FF5+UMD
alpha, and clarity of economic rationale.

The paper therefore reports both candidate-level results and family-level
results. This distinction is important because a 300-candidate LLM pool may
generate many variants of "mispricing plus financing discipline" or "quality
plus value plus momentum." Family-level reporting makes the discovery process
more conservative and interpretable.

### 5.7 Method-Level Evaluation

The AI contribution is evaluated at the method level. The paper does not only
ask whether the best LLM factor is significant. It asks whether the LLM
candidate-generation process produces more valid, interpretable, and OOS-robust
factor families than budget-matched GP search.

The main method-level table reports attempted candidates, parseable
expressions, sufficient-coverage candidates, unique factor families, selected
factors, locked-OOS pass rate, best OOS alpha t-statistic, average OOS IC, and
average economic-rationale quality where applicable. This is the table that
turns the paper from a standard factor paper into an AI-finance paper.

## 6. Main Results

### 6.1 Validated LLM Factors

The strict validation gate identifies six LLM-generated factors out of the
20-candidate extended pool. Four are the most natural headline factors because
they pass the full+OOS gate and have full-sample value-weighted FF5+UMD alpha
t-statistics above 3.0 or very close to the standard new-factor threshold.

The first is `financing_reversal_guard`:

```text
-RANK($eqnetis_at) - RANK($dbnetis_at)
+ RANK($ret_12_1) - RANK($ret_1_0)
```

This factor combines low net equity issuance, low debt issuance, intermediate
momentum, and a short-term reversal guard. It earns an annualized
value-weighted FF5+UMD alpha of 11.7% in the full sample with t=4.09 and
remains marginally significant out of sample with t=1.97.

The second is `mispricing_combo`:

```text
RANK($mispricing_perf) + RANK($mispricing_mgmt)
```

This factor earns an annualized value-weighted FF5+UMD alpha of 8.9% in the
full sample with a Newey-West t-statistic of 3.93. It remains significant out
of sample with t=2.96. The factor has a high full-sample RankIC t-statistic
of 6.97 and strongly monotone decile returns.

The third is `mispr_fin_quality`:

```text
RANK($mispricing_perf) + RANK($mispricing_mgmt)
- RANK($eqnetis_at) - RANK($at_gr1) + RANK($gp_at)
```

This factor adds profitability support to the mispricing-financing discipline
mechanism. It earns an annualized value-weighted FF5+UMD alpha of 7.3% with
t=3.50 in the full sample and remains significant out of sample with t=2.75.

The fourth is `mispr_fin_disc`:

```text
RANK($mispricing_perf) + RANK($mispricing_mgmt)
- RANK($eqnetis_at) - RANK($at_gr1)
```

This factor earns an annualized value-weighted FF5+UMD alpha of 7.5% with
t=3.41 in the full sample and remains significant out of sample with t=2.31.
Its economic interpretation is that long positions combine low mispricing risk
with financing and investment discipline, while short positions load on
overpriced, issuing, and aggressively expanding firms.

Two additional candidates pass the full+OOS factor-lab gate but are better
treated as supporting evidence because their full-sample alpha t-statistics are
below the stricter `t>3` headline threshold. `liquid_mispricing` adds liquidity
and trading-friction filters to the mispricing composite and has OOS t=2.78.
`mispr_profit_interaction` interacts mispricing-management with profitability
and has OOS t=2.02.

### 6.2 Failed but Informative Factors

The pipeline also rejects plausible factors. `qual_val_mom` has strong
full-sample alpha, but its OOS value-weighted FF5+UMD alpha t-statistic falls
to 1.94 and it fails the strict gate. `fin_inv_discipline` has strong
cross-sectional Fama-MacBeth performance but weak OOS value-weighted alpha.
`prof_trend_ts` does not produce reliable portfolio or cross-sectional
performance. These failures are important because they show that the validation
pipeline is selective and that the paper is not reporting only successful
outputs.

### 6.3 Increment Beyond Components and Known Anomalies

Spanning tests show that the validated factors are not merely mechanical
relabelings of their components. `mispricing_combo` has a significant intercept
relative to its components in the full sample and OOS, and also remains
incremental to the Kelly anomaly zoo out of sample. `mispr_fin_disc` is less
incremental relative to its own components but remains significant relative to
the broader anomaly zoo in the full sample, consistent with the idea that the
combination captures a structured interaction among mispricing, issuance, and
investment.

### 6.4 Firm-Level Evidence

Fama-MacBeth regressions confirm that the validated factors predict returns at
the firm-month level after standard controls. `mispricing_combo` has a
multivariate slope of +0.207% per month per one-standard-deviation increase,
with t=6.75. `mispr_fin_disc` has a multivariate slope of +0.184% with t=6.65.
These results indicate that the portfolio alphas are not solely artifacts of
portfolio construction.

### 6.5 Comparison with Mechanical Search

The full-grammar genetic-programming baseline searches the same expression
language using the same parser and evaluation objective. Its selected winner
does not pass the strict OOS value-weighted FF5+UMD alpha gate. The comparison
suggests that the LLM's value is not simply brute-force expression search. The
LLM appears most useful when it combines economically meaningful characteristics
into simple, interpretable hypotheses that survive later validation.

## 7. Discussion

The findings support a restrained interpretation of LLMs in empirical finance.
LLMs are not substitutes for economic theory or out-of-sample testing. They are
also not immune to data mining. Their useful role is to generate structured
candidate hypotheses that can be audited, rejected, or validated by standard
asset-pricing tools.

This distinction matters for both AI and finance. For AI, the paper shows a
concrete scientific-discovery setting where the output of a language model is
not evaluated by surface plausibility but by a locked empirical protocol. For
finance, the paper provides a way to use LLMs without abandoning the discipline
learned from the factor zoo literature: pre-specification, multiple-testing
adjustments, OOS validation, and economic interpretation.

The evidence is strongest for LLMs as synthesis engines. The validated factors
do not discover a new accounting variable; rather, they combine known economic
signals in a way that is coherent and empirically robust. This is still valuable.
Much of empirical asset pricing is about identifying when known mechanisms
interact. LLMs can help search that conceptual space, provided the search is
documented and the validation is external to the model.

## 8. Planned Robustness to Complete Before Submission

The current evidence should be strengthened before submission with the following
pre-specified additions:

1. Run two additional LLMs under the same prompt, grammar, split, and candidate
   budget.
2. Report model-level candidate accounting: attempts, valid expressions,
   duplicates, failures, selected factors, average OOS IC, and best selected
   OOS alpha.
3. Run a budget-matched 300-candidate full-grammar GP baseline.
4. Report transaction-cost and turnover-adjusted long-short returns.
5. Report liquidity-filtered and mega-cap robustness.
6. Include the prompt version, candidate ledger path, and run manifest in an
   audit appendix.

## 9. Conclusion

This paper studies whether LLMs can generate economically interpretable equity
factors that survive modern empirical asset-pricing validation. The answer is
qualified but positive. Under an auditable protocol with fixed grammars,
candidate ledgers, a locked OOS sample, mechanical-search baselines, and
multiple-testing haircuts, selected LLM-generated factors earn significant
value-weighted FF5+UMD alphas and remain predictive in firm-level regressions.

The broader lesson is methodological. LLMs should not be used as unconstrained
factor-mining machines. Used that way, they would amplify the data-mining
problem that already challenges the factor literature. Used as auditable
economic hypothesis generators, however, they can help organize financial
knowledge into testable signals. The paper's contribution is therefore both an
empirical result and a research design: a way to integrate LLMs into asset
pricing while preserving the discipline of out-of-sample validation.

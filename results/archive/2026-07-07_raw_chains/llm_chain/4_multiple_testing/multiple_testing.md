# Multiple-testing haircuts
_VW long-short. N_trials = **300** (search budget). HLZ rule: a new factor needs |t| > 3.0. Bonferroni multiplies p by N. DSR = P(Sharpe real | N trials, non-normality, sample length); pass at > 0.95._

| Factor | t (NW) | HLZ t>3 | Bonferroni p | sig@5% | SR ann | SR\* (exp-max) | DSR | DSR>0.95 |
|---|---|---|---|---|---|---|---|---|
| cash_prof_accrual_quality | +4.67*** | PASS | 0.001 | PASS | +0.65 | +0.55 | 0.764 | FAIL |
| quality_bloat_value | +4.38*** | PASS | 0.004 | PASS | +0.62 | +0.55 | 0.681 | FAIL |
| shareholder_yield_quality | +3.58*** | PASS | 0.102 | FAIL | +0.60 | +0.55 | 0.632 | FAIL |
| ev_value_cash_profitability | +3.43*** | PASS | 0.182 | FAIL | +0.50 | +0.55 | 0.349 | FAIL |
| pead_earnings_revenue_surprise | +3.01*** | PASS | 0.788 | FAIL | +0.44 | +0.55 | 0.197 | FAIL |
| accrual_investment_discipline | +2.86*** | FAIL | 1.000 | FAIL | +0.39 | +0.55 | 0.120 | FAIL |
| earnings_streak_momentum | +2.63*** | FAIL | 1.000 | FAIL | +0.36 | +0.55 | 0.087 | FAIL |
| profitability_minus_lottery | +1.89* | FAIL | 1.000 | FAIL | +0.27 | +0.55 | 0.022 | FAIL |
| distress_adjusted_value | +0.96 | FAIL | 1.000 | FAIL | +0.14 | +0.55 | 0.001 | FAIL |
| low_duration_quality | +0.71 | FAIL | 1.000 | FAIL | +0.11 | +0.55 | 0.001 | FAIL |
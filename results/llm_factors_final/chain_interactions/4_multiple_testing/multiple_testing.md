# Multiple-testing haircuts
_VW long-short. N_trials = **300** (search budget). HLZ rule: a new factor needs |t| > 3.0. Bonferroni multiplies p by N. DSR = P(Sharpe real | N trials, non-normality, sample length); pass at > 0.95._

| Factor | t (NW) | HLZ t>3 | Bonferroni p | sig@5% | SR ann | SR\* (exp-max) | DSR | DSR>0.95 |
|---|---|---|---|---|---|---|---|---|
| persistent_mispricing_disc | +4.64*** | PASS | 0.001 | PASS | +0.67 | +0.78 | 0.214 | FAIL |
| riskadj_momentum_disc | +3.75*** | PASS | 0.054 | FAIL | +0.50 | +0.78 | 0.023 | FAIL |
| cashprof_per_investment | +3.60*** | PASS | 0.094 | FAIL | +0.55 | +0.78 | 0.035 | FAIL |
| earnings_yield_stability | +3.44*** | PASS | 0.176 | FAIL | +0.54 | +0.78 | 0.036 | FAIL |
| accrual_deterioration_guard | +3.10*** | PASS | 0.585 | FAIL | +0.46 | +0.78 | 0.008 | FAIL |
| mispr_x_cashprof | +1.99** | FAIL | 1.000 | FAIL | +0.27 | +0.78 | 0.000 | FAIL |
| cashprof_trend_value | +1.98** | FAIL | 1.000 | FAIL | +0.30 | +0.78 | 0.000 | FAIL |
| value_x_quality | +1.81* | FAIL | 1.000 | FAIL | +0.26 | +0.78 | 0.000 | FAIL |
| profit_accel_x_value | -1.40 | FAIL | 1.000 | FAIL | -0.21 | +0.78 | 0.000 | FAIL |
| surprise_x_illiquidity | +0.13 | FAIL | 1.000 | FAIL | +0.02 | +0.78 | 0.000 | FAIL |
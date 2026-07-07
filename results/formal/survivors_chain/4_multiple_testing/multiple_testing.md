# Multiple-testing haircuts
_VW long-short. N_trials = **300** (search budget). HLZ rule: a new factor needs |t| > 3.0. Bonferroni multiplies p by N. DSR = P(Sharpe real | N trials, non-normality, sample length); pass at > 0.95._

| Factor | t (NW) | HLZ t>3 | Bonferroni p | sig@5% | SR ann | SR\* (exp-max) | DSR | DSR>0.95 |
|---|---|---|---|---|---|---|---|---|
| cash_prof_accrual_quality | +4.67*** | PASS | 0.001 | PASS | +0.65 | +0.15 | 1.000 | PASS |
| persistent_mispricing_disc | +4.64*** | PASS | 0.001 | PASS | +0.67 | +0.15 | 1.000 | PASS |
| quality_bloat_value | +4.38*** | PASS | 0.004 | PASS | +0.62 | +0.15 | 1.000 | PASS |
| shareholder_yield_quality | +3.58*** | PASS | 0.102 | FAIL | +0.60 | +0.15 | 1.000 | PASS |
| earnings_yield_stability | +3.44*** | PASS | 0.176 | FAIL | +0.54 | +0.15 | 0.998 | PASS |
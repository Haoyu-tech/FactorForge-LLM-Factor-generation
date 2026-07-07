# Multiple-testing haircuts
_VW long-short. N_trials = **300** (search budget). HLZ rule: a new factor needs |t| > 3.0. Bonferroni multiplies p by N. DSR = P(Sharpe real | N trials, non-normality, sample length); pass at > 0.95._

| Factor | t (NW) | HLZ t>3 | Bonferroni p | sig@5% | SR ann | SR\* (exp-max) | DSR | DSR>0.95 |
|---|---|---|---|---|---|---|---|---|
| debt_discipline_value | +5.08*** | PASS | 0.000 | PASS | +0.63 | +0.16 | 1.000 | PASS |
| issuance_mom_reversal | +4.87*** | PASS | 0.000 | PASS | +0.71 | +0.16 | 1.000 | PASS |
| mispr_noa_disc | +4.81*** | PASS | 0.000 | PASS | +0.71 | +0.16 | 1.000 | PASS |
| cash_prof_accrual_quality | +4.67*** | PASS | 0.001 | PASS | +0.65 | +0.16 | 1.000 | PASS |
| coa_growth_quality | +4.40*** | PASS | 0.003 | PASS | +0.56 | +0.16 | 0.998 | PASS |
| quality_bloat_value | +4.38*** | PASS | 0.004 | PASS | +0.62 | +0.16 | 1.000 | PASS |
| ebitda_value_quality | +4.19*** | PASS | 0.008 | PASS | +0.69 | +0.16 | 1.000 | PASS |
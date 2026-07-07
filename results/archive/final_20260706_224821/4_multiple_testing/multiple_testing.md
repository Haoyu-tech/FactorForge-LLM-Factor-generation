# Multiple-testing haircuts
_VW long-short. N_trials = **10** (search budget). HLZ rule: a new factor needs |t| > 3.0. Bonferroni multiplies p by N. DSR = P(Sharpe real | N trials, non-normality, sample length); pass at > 0.95._

| Factor | t (NW) | HLZ t>3 | Bonferroni p | sig@5% | SR ann | SR\* (exp-max) | DSR | DSR>0.95 |
|---|---|---|---|---|---|---|---|---|
| qual_val_mom | +4.67*** | PASS | 0.000 | PASS | +0.66 | +0.38 | 0.980 | PASS |
| mispricing_combo | +3.94*** | PASS | 0.001 | PASS | +0.54 | +0.38 | 0.887 | FAIL |
| mispr_fin_disc | +3.82*** | PASS | 0.001 | PASS | +0.57 | +0.38 | 0.924 | FAIL |
| fin_inv_discipline | +2.14** | FAIL | 0.325 | FAIL | +0.31 | +0.38 | 0.322 | FAIL |
| prof_trend_ts | +0.50 | FAIL | 1.000 | FAIL | +0.07 | +0.38 | 0.013 | FAIL |
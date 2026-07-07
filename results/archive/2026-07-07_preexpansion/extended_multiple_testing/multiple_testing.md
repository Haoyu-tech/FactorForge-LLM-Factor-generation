# Multiple-testing haircuts
_VW long-short. N_trials = **20** (search budget). HLZ rule: a new factor needs |t| > 3.0. Bonferroni multiplies p by N. DSR = P(Sharpe real | N trials, non-normality, sample length); pass at > 0.95._

| Factor | t (NW) | HLZ t>3 | Bonferroni p | sig@5% | SR ann | SR\* (exp-max) | DSR | DSR>0.95 |
|---|---|---|---|---|---|---|---|---|
| financing_reversal_guard | +4.87*** | PASS | 0.000 | PASS | +0.71 | +0.37 | 0.993 | PASS |
| qual_val_mom | +4.67*** | PASS | 0.000 | PASS | +0.66 | +0.37 | 0.983 | PASS |
| mispricing_trend_discipline | +4.12*** | PASS | 0.001 | PASS | +0.59 | +0.37 | 0.954 | PASS |
| mispricing_combo | +3.94*** | PASS | 0.002 | PASS | +0.54 | +0.37 | 0.901 | FAIL |
| mispr_fin_disc | +3.82*** | PASS | 0.003 | PASS | +0.57 | +0.37 | 0.935 | FAIL |
| mispr_lowrisk_disc | +3.76*** | PASS | 0.003 | PASS | +0.56 | +0.37 | 0.924 | FAIL |
| issuance_trend_reversal | +3.62*** | PASS | 0.006 | PASS | +0.55 | +0.37 | 0.902 | FAIL |
| mispr_fin_quality | +3.57*** | PASS | 0.007 | PASS | +0.53 | +0.37 | 0.886 | FAIL |
| risk_adjusted_fin_disc | +3.28*** | PASS | 0.021 | PASS | +0.47 | +0.37 | 0.766 | FAIL |
| investment_quality_ratio | +3.16*** | PASS | 0.031 | PASS | +0.53 | +0.37 | 0.897 | FAIL |
| mispr_profit_interaction | +3.10*** | PASS | 0.039 | PASS | +0.47 | +0.37 | 0.789 | FAIL |
| cheap_prof_lowissue | +3.03*** | PASS | 0.048 | PASS | +0.52 | +0.37 | 0.885 | FAIL |
| value_profit_ratio_stable | +2.56** | FAIL | 0.207 | FAIL | +0.42 | +0.37 | 0.651 | FAIL |
| liquid_mispricing | +2.55** | FAIL | 0.212 | FAIL | +0.33 | +0.37 | 0.407 | FAIL |
| quality_trend_value | +2.55** | FAIL | 0.216 | FAIL | +0.39 | +0.37 | 0.587 | FAIL |
| fin_inv_discipline | +2.14** | FAIL | 0.651 | FAIL | +0.31 | +0.37 | 0.351 | FAIL |
| profitability_acceleration_value | +0.85 | FAIL | 1.000 | FAIL | +0.12 | +0.37 | 0.038 | FAIL |
| value_mom_stability | +0.83 | FAIL | 1.000 | FAIL | +0.12 | +0.37 | 0.039 | FAIL |
| safe_value_prof | +0.72 | FAIL | 1.000 | FAIL | +0.11 | +0.37 | 0.031 | FAIL |
| prof_trend_ts | +0.50 | FAIL | 1.000 | FAIL | +0.07 | +0.37 | 0.016 | FAIL |
# Candidate survival distribution

Run: `D:/桌面文件/文章/LLM-Factor/results/manual_llm_diverse_pass_100`

## Survival funnel (strict gate)

| Stage | Count |
|---|---:|
| gated | 54 |
| full_sample_alpha_sig | 37 |
| oos_alpha_sig (== factor_lab PASS) | 16 |
| oos_decay_full_to_pass | 37 -> 16 (43% of full-sig survive OOS) |
| diversity_rejected | 19 |
| diverse_survivors | 3 |

## By expression structure

Additive rank-sums survive; multiplicative interactions and ratios mostly do not.

| structure      |   gated |   full_sig |   oos_sig(PASS) |   median_full_t |   median_oos_t |   oos_pass_rate |
|:---------------|--------:|-----------:|----------------:|----------------:|---------------:|----------------:|
| timeseries     |      28 |         25 |              14 |            3.45 |           1.95 |            0.5  |
| ratio          |      13 |          7 |               0 |            2.2  |           1.01 |            0    |
| multiplicative |       7 |          1 |               0 |            0.89 |           0.19 |            0    |
| rank_sum       |       6 |          4 |               2 |            2.64 |           1.41 |            0.33 |

## By economic family

| family                               |   gated |   full_sig |   oos_sig(PASS) |   median_full_t |   median_oos_t |   oos_pass_rate |
|:-------------------------------------|--------:|-----------:|----------------:|----------------:|---------------:|----------------:|
| mispricing_financing_ts              |       7 |          7 |               5 |            3.44 |           2.39 |            0.71 |
| strict_issuance_momentum_quality     |       4 |          4 |               0 |            3.57 |           1.79 |            0    |
| strict_mispricing_financing_quality  |       4 |          4 |               3 |            3.37 |           2.46 |            0.75 |
| strict_mispricing_financing          |       4 |          4 |               4 |            3.69 |           2.51 |            1    |
| strict_issuance_momentum             |       4 |          3 |               1 |            3.14 |           1.82 |            0.25 |
| issuance_momentum_ts                 |       3 |          3 |               1 |            3.92 |           1.66 |            0.33 |
| strict_value_quality_issuance        |       3 |          3 |               1 |            3.02 |           1.23 |            0.33 |
| strict_profitability_efficiency      |       3 |          3 |               0 |            2.51 |           1.26 |            0    |
| risk_scaled_ratio                    |       3 |          0 |               0 |            0.65 |          -0.01 |            0    |
| profitability_efficiency_ratio       |       3 |          3 |               0 |            3.17 |           1.68 |            0    |
| strict_value_quality_interaction     |       3 |          1 |               0 |            1.51 |           0.36 |            0    |
| liquidity_guard                      |       2 |          0 |               0 |            1.11 |           1.27 |            0    |
| multiplicative_interaction           |       2 |          0 |               0 |            1    |          -0.3  |            0    |
| profitability_efficiency_interaction |       2 |          0 |               0 |            0.37 |          -0.04 |            0    |
| strict_risk_scaled_quality           |       2 |          0 |               0 |            1.33 |           0.27 |            0    |
| strict_risk_scaled_mispricing        |       2 |          1 |               0 |            2.07 |           1.02 |            0    |
| trend_interaction                    |       2 |          0 |               0 |            1.45 |          -0.19 |            0    |
| rank_sum_calibration                 |       1 |          1 |               1 |            4.09 |           1.97 |            1    |

## OOS decay among full-sample-significant candidates

| Metric | Value |
|---|---:|
| full_sig_candidates | 37 |
| median_full_t_among_full_sig | 3.44 |
| median_oos_t_among_full_sig | 1.85 |
| share_oos_t_below_1.96 | 0.57 |

_Interpretation: the strict OOS + diversity screens collapse a large pool of full-sample-significant, economically-motivated composites down to a few mutually uncorrelated survivors -- all variants of one mispricing/financing-discipline mechanism. The candidate distribution, not the winners, is the auditable result._

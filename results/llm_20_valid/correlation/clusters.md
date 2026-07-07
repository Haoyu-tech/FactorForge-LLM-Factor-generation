# Correlation clustering of the 20 valid factors

Pairwise correlation of value-weighted decile long-short MONTHLY RETURNS (1972-2025, n=647 months). Agglomerative clustering (average linkage); factors with return correlation > 0.6 are grouped.

## 7 independent directions (corr>0.6 clusters)

| Cluster | # | Representative (max full t) | Members |
|--:|--:|---|---|
| 6 | 8 | **mispr_noa_disc** (t=+4.10) | mispr_fin_disc, mispr_fin_disc_quality, ev_value_cashprof, persistent_mispricing_disc, mispr_profit_lowrisk, mispr_fin_disc_op, mispr_sale_growth_disc |
| 4 | 4 | **ebitda_value_quality** (t=+3.83) | cashprof_lowissue_value, shareholder_yield_quality, earnings_yield_stability |
| 5 | 3 | **cash_prof_accrual_quality** (t=+4.82) | mispr_mgmt_accrual, cashprof_taccruals_disc |
| 3 | 2 | **quality_bloat_value** (t=+3.67) | quality_growth_value |
| 7 | 1 | **issuance_mom_reversal** (t=+4.07) | (only rep) |
| 1 | 1 | **debt_discipline_value** (t=+4.79) | (only rep) |
| 2 | 1 | **coa_growth_quality** (t=+3.96) | (only rep) |

## Correlation summary
- mean pairwise |corr|: 0.45
- max pairwise corr: 0.92
- 7 clusters at corr>0.6  (20 factors collapse to 7 independent directions)
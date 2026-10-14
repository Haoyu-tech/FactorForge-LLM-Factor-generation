# 20 valid LLM-generated factors

[Project overview](../../README.md) · [Reproduction guide](../../docs/REPRODUCIBILITY.md)

> **Recorded research artifacts.** Interpret tables and figures using this run's data and validation settings.


Factors proposed by the LLM (Claude as LLM) from the expanded 120-factor Kelly pool, each PASSing the strict factor_lab gate: economic rationale + value-weighted FF5+UMD alpha significant in BOTH full sample (1972-2025) and OOS (post-2000), monotone deciles, OOS-IC sign persistence.

| # | Factor | VW FF5+UMD a (ann) | t full | t OOS | Expression |
|--:|---|--:|--:|--:|---|
| 1 | cash_prof_accrual_quality | +9.9% | +4.82 | +2.71 | `RANK($cop_at) - RANK($oaccruals_at) - RANK($eqnetis_at)` |
| 2 | debt_discipline_value | +8.7% | +4.79 | +3.22 | `-RANK($dbnetis_at) - RANK($debt_me) + RANK($be_me) + RANK($cop_at)` |
| 3 | mispr_mgmt_accrual | +9.8% | +4.74 | +3.79 | `RANK($mispricing_mgmt) - RANK($oaccruals_at) - RANK($eqnetis_at) + RANK($gp_at)` |
| 4 | mispr_noa_disc | +8.1% | +4.10 | +3.75 | `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($noa_at)` |
| 5 | issuance_mom_reversal | +11.6% | +4.07 | +1.97 | `-RANK($eqnetis_at) - RANK($dbnetis_at) + RANK($ret_12_1) - RANK($ret_1_0)` |
| 6 | persistent_mispricing_disc | +8.7% | +4.02 | +2.64 | `RANK(TS_MEAN($mispricing_perf, 6) + TS_MEAN($mispricing_mgmt, 6)) - RANK(TS_MEAN($eqnetis_at, 12))` |
| 7 | coa_growth_quality | +6.9% | +3.96 | +3.04 | `-RANK($coa_gr1a) - RANK($at_gr1) + RANK($cop_at)` |
| 8 | ebitda_value_quality | +10.2% | +3.83 | +3.62 | `RANK($ebitda_mev) + RANK($qmj_prof) - RANK($eqnetis_at)` |
| 9 | cashprof_taccruals_disc | +7.7% | +3.76 | +1.96 | `RANK($cop_at) - RANK($taccruals_at) - RANK($eqnetis_at)` |
| 10 | quality_bloat_value | +7.1% | +3.67 | +2.79 | `RANK($qmj_prof) + RANK($qmj_safety) + RANK($sale_me) - RANK($noa_at)` |
| 11 | mispr_fin_disc_quality | +7.5% | +3.63 | +2.75 | `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1) + RANK($gp_at)` |
| 12 | mispr_sale_growth_disc | +7.6% | +3.55 | +2.45 | `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($sale_gr1)` |
| 13 | cashprof_lowissue_value | +9.0% | +3.54 | +1.99 | `RANK($cop_at) + RANK($be_me) - RANK($eqnetis_at) - RANK($chcsho_12m)` |
| 14 | mispr_fin_disc | +7.5% | +3.47 | +2.31 | `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1)` |
| 15 | ev_value_cashprof | +6.6% | +3.47 | +3.37 | `RANK($ebit_bev) + RANK($cop_at) - RANK($at_gr1)` |
| 16 | quality_growth_value | +6.3% | +3.37 | +3.46 | `RANK($qmj_prof) + RANK($ni_be) + RANK($sale_me) - RANK($noa_at)` |
| 17 | mispr_fin_disc_op | +6.9% | +3.30 | +2.23 | `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1) + RANK($op_at)` |
| 18 | earnings_yield_stability | +7.3% | +3.27 | +2.49 | `RANK($ni_me / ($ni_ivol + 1)) + RANK($cop_at)` |
| 19 | shareholder_yield_quality | +8.3% | +3.22 | +2.58 | `RANK($eqnpo_me) + RANK($cop_at) - RANK($eqnetis_at)` |
| 20 | mispr_profit_lowrisk | +7.3% | +2.66 | +2.16 | `RANK($mispricing_perf) + RANK($mispricing_mgmt) + RANK($gp_at) - RANK($ivol_ff3_21d)` |

Each factor has a full bundle in `factors/<name>/`: 4-panel chart (`<name>.png`), `<name>.json`, economic derivation tree (`trees/`), and formula parse tree (`formula_trees/`). See `factors/index.md`.

NOTE: all 20 pass the gate; they are NOT all mutually uncorrelated — many share the mispricing / financing-discipline / cash-profitability mechanisms. For the diversity-screened, zoo-beating, cost-and-industry-robust subset see `results/llm_factors_final/` and `results/formal/`.

# LLM failure feedback

Use this as negative feedback for the next LLM generation round.

## Failure counts

| Reason | Count |
|---|---:|
| failed | 4 |
| high_factor_rank_correlation | 3 |

## Recent actionable feedback

### strict_mispr_fin_q_3_eqnetis_at_3_at_gr1_qmj_prof [diversity / rejected]
- **Expr:** `RANK(TS_MEAN($mispricing_perf, 3) + TS_MEAN($mispricing_mgmt, 3)) - RANK(TS_MEAN($eqnetis_at, 3)) - RANK($at_gr1) + RANK($qmj_prof)`
- **Feedback:** Reject for redundancy: too correlated with mispr_ts_fin_disc_3_6 (abs monthly rank corr=0.93). Use different source fields or a genuinely different interaction.

### strict_mispr_fin_q_3_eqnetis_at_3_at_gr1_qmj_prof [diversity / rejected]
- **Expr:** `RANK(TS_MEAN($mispricing_perf, 3) + TS_MEAN($mispricing_mgmt, 3)) - RANK(TS_MEAN($eqnetis_at, 3)) - RANK($at_gr1) + RANK($qmj_prof)`
- **Feedback:** Reject for redundancy: too correlated with mispr_ts_fin_disc_3_6 (abs monthly rank corr=0.93). Use different source fields or a genuinely different interaction.

### strict_mispr_fin_3_eqnetis_at_3_noa_at [diversity / rejected]
- **Expr:** `RANK(TS_MEAN($mispricing_perf, 3) + TS_MEAN($mispricing_mgmt, 3)) - RANK(TS_MEAN($eqnetis_at, 3)) - RANK($noa_at)`
- **Feedback:** Reject for redundancy: too correlated with mispr_ts_fin_disc_3_6 (abs monthly rank corr=0.86). Use different source fields or a genuinely different interaction.

### strict_issuance_change_mom_q_eqnetis_at_3_ret_12_1_qmj_prof [strict_gate / failed]
- **Expr:** `-RANK(TS_MEAN($eqnetis_at, 3)) - RANK(DELTA($eqnetis_at, 3)) + RANK($ret_12_1) - RANK($ret_1_0) + RANK($qmj_prof)`
- **Feedback:** Reject after full gate: OOS VW FF5+UMD alpha does not survive. Next proposal should change the economic mechanism, not just tune a window.

### strict_value_quality_issue_be_me_gp_at_chcsho_12m [strict_gate / failed]
- **Expr:** `RANK($be_me) + RANK($gp_at) - RANK($chcsho_12m) - RANK($ret_1_0)`
- **Feedback:** Reject after full gate: OOS VW FF5+UMD alpha does not survive. Next proposal should change the economic mechanism, not just tune a window.

### strict_value_quality_product_be_me_gp_at_chcsho_12m [strict_gate / failed]
- **Expr:** `RANK(ZSCORE($be_me) * ZSCORE($gp_at)) - RANK($chcsho_12m) - RANK($ret_1_0)`
- **Feedback:** Reject after full gate: full-sample VW FF5+UMD alpha is too weak; OOS VW FF5+UMD alpha does not survive. Next proposal should change the economic mechanism, not just tune a window.

### strict_issuance_change_mom_eqnetis_at_3_resff3_12_1 [strict_gate / failed]
- **Expr:** `-RANK(TS_MEAN($eqnetis_at, 3)) - RANK(DELTA($eqnetis_at, 3)) + RANK($resff3_12_1) - RANK($ret_1_0)`
- **Feedback:** Reject after full gate: OOS VW FF5+UMD alpha does not survive. Next proposal should change the economic mechanism, not just tune a window.

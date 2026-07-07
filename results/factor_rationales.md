# Factor rationale library
_Economically/financially grounded factors and their explanations. 5 total, 2 validated. Updated 2026-07-06._

## Validated (PASS): rationale + VALUE-WEIGHTED FF5+UMD alpha significant (full & OOS) + monotone decile

### mispricing_combo -- VW FF5+UMD alpha t=3.93 (OOS t=2.96), VW FF3 t=4.58, IC_t=6.97, mono=0.98
- **Expr:** `RANK($mispricing_perf) + RANK($mispricing_mgmt)`
- **Rationale:** Composite of two mispricing scores aggregating 11 anomalies; captures systematic investor over/under-reaction not explained by risk.

### mispr_fin_disc -- VW FF5+UMD alpha t=3.41 (OOS t=2.31), VW FF3 t=4.15, IC_t=8.01, mono=0.99
- **Expr:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1)`
- **Rationale:** Stambaugh-Yuan mispricing (mgmt+performance) says overpriced/overinvesting firms earn low returns; combined with q-theory (low net equity issuance & low asset growth = disciplined capital). Long cheap/disciplined, short overpriced/overissuing.

## Has rationale but failed empirical gate (FAIL)

### fin_inv_discipline -- VW FF5+UMD alpha t=1.41, OOS t=0.2
- **Expr:** `-1*RANK($eqnetis_at) - RANK($at_gr1)`
- **Rationale:** q-theory / investment-CAPM: firms that issue equity and grow assets aggressively subsequently underperform (overinvestment, market timing).

### qual_val_mom -- VW FF5+UMD alpha t=4.2, OOS t=1.94
- **Expr:** `RANK($gp_at) + RANK($be_me) + RANK($ret_12_1)`
- **Rationale:** Three independent premia: gross profitability (Novy-Marx quality), book-to-market (value risk/mispricing), 12-1 momentum (underreaction). Diversified across rationales.

### prof_trend_ts -- VW FF5+UMD alpha t=0.44, OOS t=-0.81
- **Expr:** `TS_ZSCORE($gp_at, 12)`
- **Rationale:** Hypothesis: improving profitability trend signals future returns. Included as a weak control to contrast against economically-grounded factors.

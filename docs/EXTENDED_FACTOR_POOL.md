# Extended Factor Pool Summary

This file records the expanded LLM factor pool used to address the "too few
factors" concern. The original `thesis_core` set remains the conservative main
set. The new `thesis_extended` set contains 20 economically motivated LLM
candidates gathered from the curated factors and accepted candidate ledgers.

## Candidate Accounting

| Set | Candidates | Purpose |
|---|---:|---|
| `thesis_core` | 5 | Conservative headline set |
| `thesis_extended` | 20 | Broader paper-level discovery pool |

The extended evaluation outputs are stored in:

| Output | Path |
|---|---|
| Factor lab | `results/extended_factor_lab/` |
| Multiple testing | `results/extended_multiple_testing/` |

## Extended Factor-Lab Gate

The factor-lab gate requires economic rationale, monotone full-sample deciles,
value-weighted FF5+UMD alpha significance in the full sample and OOS, and
consistent IC sign. Six of the 20 extended candidates pass this gate.

| Factor | VW FF5+UMD alpha ann | Full t | OOS t | Verdict |
|---|---:|---:|---:|---|
| financing_reversal_guard | +11.7% | +4.09 | +1.97 | PASS |
| mispricing_combo | +8.9% | +3.93 | +2.96 | PASS |
| mispr_fin_quality | +7.3% | +3.50 | +2.75 | PASS |
| mispr_fin_disc | +7.5% | +3.41 | +2.31 | PASS |
| liquid_mispricing | +5.1% | +2.71 | +2.78 | PASS |
| mispr_profit_interaction | +5.8% | +2.69 | +2.02 | PASS |

## Multiple-Testing Haircuts

Using `N_trials=20`, twelve candidates pass the full-sample HLZ `|t| > 3`
screen, twelve remain Bonferroni-significant at 5%, and three pass the Deflated
Sharpe Ratio threshold of 0.95.

| Factor | t (NW) | HLZ t>3 | Bonferroni | DSR | DSR>0.95 |
|---|---:|---|---|---:|---|
| financing_reversal_guard | +4.87 | PASS | PASS | 0.993 | PASS |
| qual_val_mom | +4.67 | PASS | PASS | 0.983 | PASS |
| mispricing_trend_discipline | +4.12 | PASS | PASS | 0.954 | PASS |
| mispricing_combo | +3.94 | PASS | PASS | 0.901 | FAIL |
| mispr_fin_disc | +3.82 | PASS | PASS | 0.935 | FAIL |
| mispr_lowrisk_disc | +3.76 | PASS | PASS | 0.924 | FAIL |
| issuance_trend_reversal | +3.62 | PASS | PASS | 0.902 | FAIL |
| mispr_fin_quality | +3.57 | PASS | PASS | 0.886 | FAIL |
| risk_adjusted_fin_disc | +3.28 | PASS | PASS | 0.766 | FAIL |
| investment_quality_ratio | +3.16 | PASS | PASS | 0.897 | FAIL |
| mispr_profit_interaction | +3.10 | PASS | PASS | 0.789 | FAIL |
| cheap_prof_lowissue | +3.03 | PASS | PASS | 0.885 | FAIL |

## Paper Positioning

The expanded pool changes the empirical story:

1. The project is no longer a 5-factor demonstration.
2. The paper can report a 20-candidate LLM discovery pool.
3. The main table can emphasize the strongest 4-6 validated factors.
4. Failed candidates remain visible, which strengthens the auditability claim.

Recommended interpretation:

> We evaluate 20 economically motivated LLM-generated candidate factors. Six
> pass the full+OOS factor-lab gate, while twelve pass the full-sample HLZ
> multiple-testing screen under a 20-trial budget. The dispersion between
> full-sample strength and OOS survival is itself evidence that the pipeline is
> selective rather than winner-only.

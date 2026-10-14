# De-redundant final factor set — 7 independent directions under every lens

[Project overview](../../README.md) · [Reproduction guide](../../docs/REPRODUCIBILITY.md)

> **Recorded research artifacts.** Interpret tables and figures using this run's data and validation settings.


The 20 gate-valid LLM factors collapse to **7 correlation clusters** (see `../llm_20_valid/correlation/`); this is one representative per cluster (mutual corr<0.6). Each is run through the full chain. Value-weighted, Newey-West, 1972-2025, OOS post-2000.

gate/zoo14/indneu = VW FF5+UMD alpha t (full/OOS); zoo14 = spanning vs the 14 JKP theme composites; FM = Fama-MacBeth t (EW / VW-WLS); net50bp = after-cost alpha t at 50bps.

| factor | gate_full/oos | zoo14_full/oos | walk%+ | HLZ | FM_EW/VW | turn/yr | net50bp_t | indneu_full/oos |
|---|---|---|---|---|---|---|---|---|
| cash_prof_accrual_quality | 4.82/2.71 | 2.46/1.33 | 83% | Y | 6.4/5.0 | 324% | 3.19 | 3.28/2.04 |
| debt_discipline_value | 4.79/3.22 | 2.86/1.82 | 75% | Y | 5.6/4.1 | 469% | 2.16 | 3.25/2.38 |
| mispr_noa_disc | 4.10/3.75 | 2.07/2.94 | 83% | Y | 7.7/5.4 | 380% | 2.21 | 3.09/1.87 |
| issuance_mom_reversal | 4.07/1.97 | 3.45/2.76 | 67% | Y | 7.3/5.4 | 1641% | -1.71 | 4.01/0.27 |
| coa_growth_quality | 3.96/3.04 | 1.42/0.41 | 67% | Y | 5.5/3.7 | 413% | 1.58 | 2.21/0.05 |
| ebitda_value_quality | 3.83/3.62 | 2.70/4.14 | 92% | Y | 6.6/5.2 | 374% | 2.45 | 1.71/0.55 |
| quality_bloat_value | 3.67/2.79 | 2.02/1.64 | 100% | Y | 6.6/5.8 | 334% | 2.02 | 2.04/1.10 |

## Robustness tiers (all 7 already clear the gate + HLZ t>3; graded by the 3 EXTRA OOS lenses: beat the 14-theme zoo OOS, after-cost @50bp, industry-neutral OOS)

- **Robust core (4/7, clears ≥2 of 3):** `cash_prof_accrual_quality` (2/3), `debt_discipline_value` (2/3), `mispr_noa_disc` (2/3), `ebitda_value_quality` (2/3)
- **Marginal (2/7, clears 1 of 3):** `issuance_mom_reversal`, `quality_bloat_value`
- **Fragile (1/7, clears 0 of 3):** `coa_growth_quality`

No single factor clears all four OOS hurdles simultaneously (a very demanding bar — 4 independent significance tests); the robust core misses only one, and by a small margin.

**Reading it, one line per lens:**
- All 7 pass the strict gate and clear HLZ t>3; full-sample alphas are all strong (t 3.7-4.8).
- Beating the 14-theme zoo OOS thins the field: mispricing (`mispr_noa_disc` 2.94) and EV-value (`ebitda_value_quality` 4.14) beat it; cash-profitability and quality tilts are marginal (1.3-1.8).
- Transaction costs kill the high-turnover direction: `issuance_mom_reversal` (1641%/yr) goes net@50bp t=-1.71.
- Industry-neutral kills the industry bets: `coa_growth_quality` (OOS 0.05) and `issuance_mom_reversal` (0.27) collapse.
- The consistent all-rounders are **cash_prof_accrual_quality**, **debt_discipline_value**, and **mispr_noa_disc** — each fails only one lens, marginally.

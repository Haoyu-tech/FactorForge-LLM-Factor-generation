# Formal evaluation — LLM vs mechanical search on the 120-factor pool

[Project overview](../../README.md) · [Reproduction guide](../../docs/REPRODUCIBILITY.md)

> **Recorded research artifacts.** Interpret tables and figures using this run's data and validation settings.


Same 124-field pool, same fast_full grammar, same objective (selection RankIC 1972-01..2000-12), same OOS (>2000-12). Value-weighted, Newey-West throughout.

## Horse race: LLM economic factors vs full-grammar GP search

| Side | best selection IC | OOS IC | strict gate |
|---|--:|--:|---|
| LLM (economic, 5 survivors) | +0.0493 | up to +0.0228 | 5/5 PASS |
| GP mechanical search | +0.0493 | +0.0065 | FAIL (OOS a_t=1.21) |

**Punchline:** mechanical search WINS in-sample (higher selection IC) but its winner is an uninterpretable overfit that collapses out-of-sample and FAILS the strict gate, while the LLM's economically-motivated factors survive. Economic priors buy OOS robustness, not higher in-sample IC.

## The 5 LLM survivors under every lens

gate/zoo14/indneu = VW FF5+UMD alpha t (full/OOS); zoo14 = spanning vs the 14 JKP theme composites; FM = Fama-MacBeth t (EW / VW-WLS); net50bps = after-cost alpha t at 50bps.

| factor | gate_full/oos | zoo14_full/oos | walk%+ | HLZ_t3 | FM_EW/VW | net50bps_t | indneu_full/oos |
|---|---|---|---|---|---|---|---|
| cash_prof_accrual_quality | 4.82/2.71 | 2.46/1.33 | 83% | True | 6.4/5.0 | 3.19 | 3.28/2.04 |
| earnings_yield_stability | 3.27/2.49 | 1.18/2.21 | 92% | True | 6.2/5.2 | 1.42 | 3.49/2.13 |
| quality_bloat_value | 3.67/2.79 | 2.02/1.64 | 100% | True | 6.6/5.8 | 2.02 | 2.04/1.10 |
| shareholder_yield_quality | 3.22/2.58 | 0.70/1.48 | 92% | True | 6.9/5.0 | 2.03 | 2.70/1.62 |
| persistent_mispricing_disc | 4.02/2.64 | 2.54/2.25 | 92% | True | 6.4/4.9 | 2.94 | 1.28/-0.29 |

**Reading it:** no single factor wins every lens — that is the honest result.
- `cash_prof_accrual_quality` is the most robust all-rounder (beats gate, survives costs at 50bps t=3.2, and industry-neutral).
- `persistent_mispricing_disc` beats the 14-theme zoo best but is largely an INDUSTRY bet (industry-neutral OOS -0.29).
- `earnings_yield_stability` (a ratio) is not additive and is not an industry bet (industry-neutral strengthens it).
- All clear HLZ t>3 and stay significant value-weighted at the firm level (FM VW).

## Folders
- `horse_race/` — LLM vs GP full-grammar search (+ `gate/` = GP winner through the strict gate)
- `survivors_chain/` — gate, spanning (14-theme zoo), walk-forward, multiple-testing, Fama-MacBeth (EW+VW)
- `transaction_costs/` — turnover + after-cost alpha (10/25/50 bps)
- `industry_neutral/` — FF49 industry-neutral alpha
- `survivors_multilens.csv` — the combined table above

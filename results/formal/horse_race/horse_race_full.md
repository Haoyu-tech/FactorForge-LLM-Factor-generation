# Horse race (FULL GRAMMAR): LLM vs strong mechanical search
_Expression trees over the full operator set (depth 2), same engine (compute_factor), same objective (selection RankIC 1972-01-01..2000-12-31), same OOS (>2000-12-31). LLM best selection IC = +0.0391._

## LLM factors

| Factor | sel IC | OOS IC |
|---|---|---|
| cash_prof_accrual_quality | +0.0293 | +0.0144 |
| quality_bloat_value | +0.0306 | +0.0215 |
| shareholder_yield_quality | +0.0352 | +0.0214 |
| earnings_yield_stability | +0.0391 | +0.0171 |
| persistent_mispricing_disc | +0.0337 | +0.0228 |

## Search winners

| Method | best sel IC | OOS IC | trials to LLM-best sel IC | expression |
|---|---|---|---|---|
| Genetic (full) | +0.0493 | +0.0065 | 180 | `-RANK(($inv_gr1a * ($dolvol_126d + $ocf_at_chg1))) +RANK($seas_2_5an) +RANK($ret_12_1)` |
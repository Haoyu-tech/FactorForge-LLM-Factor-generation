# Horse race (FULL GRAMMAR): LLM vs strong mechanical search
_Expression trees over the full operator set (depth 2), same engine (compute_factor), same objective (selection RankIC 1972-07-01..2000-12-31), same OOS (>2000-12-31). LLM best selection IC = +0.0373._

## LLM factors

| Factor | sel IC | OOS IC |
|---|---|---|
| mispricing_combo | +0.0358 | +0.0208 |
| mispr_fin_disc | +0.0356 | +0.0196 |
| qual_val_mom | +0.0373 | +0.0150 |

## Search winners

| Method | best sel IC | OOS IC | trials to LLM-best sel IC | expression |
|---|---|---|---|---|
| Genetic (full) | +0.0290 | +0.0220 | >20 | `RANK(TS_MEAN($mispricing_mgmt, 6)) +RANK((TS_MEAN($ni_me, 36) / (TS_MAX($dolvol_126d, 3) - TS_MAX($return, 24))))` |
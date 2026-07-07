# Fama-MacBeth cross-sectional regressions
_Monthly cross-sectional OLS of next-month return on z-scored predictors, 1972-07-01..end. Slopes = monthly % return per 1 SD; Newey-West (6) t in parens. \*/\*\*/\*\*\* = 10/5/1%._

## Each factor: univariate vs with controls (size, B/M, momentum, beta)

| Factor | Univariate | + controls | avg R2 | T |
|---|---|---|---|---|
| mispr_fin_disc | +0.227*** (+6.24) | +0.184*** (+6.65) | 0.108 | 641 |
| mispricing_combo | +0.189*** (+4.56) | +0.207*** (+6.75) | 0.106 | 641 |
| fin_inv_discipline | +0.191*** (+5.01) | +0.128*** (+4.74) | 0.108 | 641 |
| qual_val_mom | +0.219*** (+4.39) | +0.170*** (+4.38) | 0.107 | 641 |
| prof_trend_ts | +0.007 (+0.25) | +0.015 (+0.81) | 0.103 | 641 |

## Controls-only baseline (the classic FM slopes)

| Variable | slope (t) |
|---|---|
| size | -0.121*** (-2.74) |
| bm | +0.104** (+2.28) |
| mom | +0.147*** (+2.62) |
| beta | -0.007 (-0.10) |
| (avg R2 0.100, T 641) | |
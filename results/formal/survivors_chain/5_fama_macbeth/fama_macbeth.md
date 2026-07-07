# Fama-MacBeth cross-sectional regressions
_Monthly cross-sectional OLS of next-month return on z-scored predictors, 1972-01-01..end. Slopes = monthly % return per 1 SD; Newey-West (6) t in parens. \*/\*\*/\*\*\* = 10/5/1%._

## Each factor: univariate vs with controls (size, B/M, momentum, beta)

_EW = equal-weighted (OLS) cross-section; VW = value-weighted (WLS, market-cap weights) cross-section, aligned with the value-weighted portfolio sort._

| Factor | Univariate (EW) | + controls (EW) | + controls (VW/WLS) | avg R2 | T |
|---|---|---|---|---|---|
| cash_prof_accrual_quality | +0.215*** (+6.71) | +0.199*** (+6.42) | +0.185*** (+5.03) | 0.108 | 647 |
| shareholder_yield_quality | +0.225*** (+6.04) | +0.204*** (+6.90) | +0.180*** (+5.00) | 0.108 | 647 |
| quality_bloat_value | +0.194*** (+5.70) | +0.194*** (+6.58) | +0.180*** (+5.84) | 0.107 | 647 |
| earnings_yield_stability | +0.194*** (+4.74) | +0.205*** (+6.16) | +0.199*** (+5.18) | 0.107 | 647 |
| persistent_mispricing_disc | +0.202*** (+4.82) | +0.199*** (+6.37) | +0.178*** (+4.86) | 0.108 | 647 |

## Controls-only baseline (the classic FM slopes)

| Variable | slope (t) |
|---|---|
| size | -0.118*** (-2.66) |
| bm | +0.103** (+2.26) |
| mom | +0.153*** (+2.76) |
| beta | -0.010 (-0.14) |
| (avg R2 0.099, T 647) | |
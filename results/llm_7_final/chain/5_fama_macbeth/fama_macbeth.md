# Fama-MacBeth cross-sectional regressions
_Monthly cross-sectional OLS of next-month return on z-scored predictors, 1972-01-01..end. Slopes = monthly % return per 1 SD; Newey-West (6) t in parens. \*/\*\*/\*\*\* = 10/5/1%._

## Each factor: univariate vs with controls (size, B/M, momentum, beta)

_EW = equal-weighted (OLS) cross-section; VW = value-weighted (WLS, market-cap weights) cross-section, aligned with the value-weighted portfolio sort._

| Factor | Univariate (EW) | + controls (EW) | + controls (VW/WLS) | avg R2 | T |
|---|---|---|---|---|---|
| mispr_noa_disc | +0.229*** (+6.99) | +0.208*** (+7.71) | +0.182*** (+5.40) | 0.109 | 647 |
| ebitda_value_quality | +0.216*** (+4.72) | +0.220*** (+6.56) | +0.203*** (+5.19) | 0.109 | 647 |
| cash_prof_accrual_quality | +0.215*** (+6.71) | +0.199*** (+6.42) | +0.185*** (+5.03) | 0.108 | 647 |
| quality_bloat_value | +0.194*** (+5.70) | +0.194*** (+6.58) | +0.180*** (+5.84) | 0.107 | 647 |
| issuance_mom_reversal | +0.255*** (+5.11) | +0.283*** (+7.30) | +0.232*** (+5.42) | 0.109 | 647 |
| debt_discipline_value | +0.173*** (+5.49) | +0.157*** (+5.58) | +0.134*** (+4.05) | 0.106 | 647 |
| coa_growth_quality | +0.192*** (+6.10) | +0.144*** (+5.47) | +0.115*** (+3.66) | 0.105 | 647 |

## Controls-only baseline (the classic FM slopes)

| Variable | slope (t) |
|---|---|
| size | -0.118*** (-2.66) |
| bm | +0.103** (+2.26) |
| mom | +0.153*** (+2.76) |
| beta | -0.010 (-0.14) |
| (avg R2 0.099, T 647) | |
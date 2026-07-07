# Fama-MacBeth cross-sectional regressions
_Monthly cross-sectional OLS of next-month return on z-scored predictors, 1972-01-01..end. Slopes = monthly % return per 1 SD; Newey-West (6) t in parens. \*/\*\*/\*\*\* = 10/5/1%._

## Each factor: univariate vs with controls (size, B/M, momentum, beta)

| Factor | Univariate | + controls | avg R2 | T |
|---|---|---|---|---|
| mispr_x_cashprof | +0.076*** (+2.58) | +0.057** (+2.44) | 0.106 | 647 |
| value_x_quality | +0.091*** (+3.47) | +0.084*** (+3.52) | 0.105 | 647 |
| surprise_x_illiquidity | +0.075* (+1.81) | +0.114*** (+3.60) | 0.107 | 647 |
| cashprof_per_investment | +0.204*** (+5.71) | +0.206*** (+6.42) | 0.108 | 647 |
| riskadj_momentum_disc | +0.230*** (+4.08) | +0.248*** (+7.10) | 0.108 | 647 |
| earnings_yield_stability | +0.194*** (+4.74) | +0.205*** (+6.16) | 0.107 | 647 |
| cashprof_trend_value | +0.202*** (+4.25) | +0.142*** (+5.06) | 0.107 | 647 |
| persistent_mispricing_disc | +0.202*** (+4.82) | +0.199*** (+6.37) | 0.108 | 647 |
| accrual_deterioration_guard | +0.180*** (+6.92) | +0.148*** (+6.21) | 0.105 | 647 |
| profit_accel_x_value | -0.038 (-0.99) | +0.033 (+1.36) | 0.104 | 647 |

## Controls-only baseline (the classic FM slopes)

| Variable | slope (t) |
|---|---|
| size | -0.118*** (-2.66) |
| bm | +0.103** (+2.26) |
| mom | +0.153*** (+2.76) |
| beta | -0.010 (-0.14) |
| (avg R2 0.099, T 647) | |
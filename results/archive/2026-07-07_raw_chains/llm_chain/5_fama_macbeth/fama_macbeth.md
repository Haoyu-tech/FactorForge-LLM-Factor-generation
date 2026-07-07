# Fama-MacBeth cross-sectional regressions
_Monthly cross-sectional OLS of next-month return on z-scored predictors, 1972-01-01..end. Slopes = monthly % return per 1 SD; Newey-West (6) t in parens. \*/\*\*/\*\*\* = 10/5/1%._

## Each factor: univariate vs with controls (size, B/M, momentum, beta)

| Factor | Univariate | + controls | avg R2 | T |
|---|---|---|---|---|
| cash_prof_accrual_quality | +0.215*** (+6.71) | +0.199*** (+6.42) | 0.108 | 647 |
| pead_earnings_revenue_surprise | +0.099*** (+2.68) | +0.121*** (+4.03) | 0.107 | 647 |
| ev_value_cash_profitability | +0.174*** (+5.56) | +0.200*** (+6.32) | 0.106 | 647 |
| low_duration_quality | +0.098 (+1.42) | +0.210*** (+4.47) | 0.109 | 647 |
| profitability_minus_lottery | +0.087 (+1.35) | +0.195*** (+5.17) | 0.107 | 647 |
| accrual_investment_discipline | +0.196*** (+5.81) | +0.154*** (+5.06) | 0.106 | 647 |
| distress_adjusted_value | +0.076 (+1.57) | +0.101*** (+3.28) | 0.107 | 647 |
| shareholder_yield_quality | +0.225*** (+6.04) | +0.204*** (+6.90) | 0.108 | 647 |
| earnings_streak_momentum | +0.133*** (+2.60) | +0.205*** (+5.51) | 0.108 | 647 |
| quality_bloat_value | +0.194*** (+5.70) | +0.194*** (+6.58) | 0.107 | 647 |

## Controls-only baseline (the classic FM slopes)

| Variable | slope (t) |
|---|---|
| size | -0.118*** (-2.66) |
| bm | +0.103** (+2.26) |
| mom | +0.153*** (+2.76) |
| beta | -0.010 (-0.14) |
| (avg R2 0.099, T 647) | |
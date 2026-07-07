# LLM-Factor - QuantaAlpha adapted to WRDS S&P 500 (monthly)

Adapts **QuantaAlpha** (LLM alpha-factor mining, originally A-share *daily* qlib
data) to our **WRDS S&P 500 *monthly* multi-factor panel**. QuantaAlpha mines
alpha *expressions*; we feed it a monthly panel whose `$`-columns include price,
size **and** ~27 fundamental/quality/value/momentum characteristics, so the LLM
can mine across data types, not just price-volume.

## Key finding about the codebase
QuantaAlpha's qlib coupling is tiny. The operator library
(`function_lib.py`) and parser (`expr_parser.py`) are **pure pandas/numpy** and
require a MultiIndex named exactly `(datetime, instrument)`:
- cross-sectional ops (`RANK`, `MEAN`, `ZSCORE`...) -> `groupby('datetime')`
- time-series ops (`TS_MEAN`, `DELTA`, `TS_CORR`...) -> `groupby('instrument')`

Only `get_qlib_stock_data()` (in `backtest/custom_factor_calculator.py`) and the
qlib backtest in `coder/eva_utils.py` actually touch qlib. Swap those and the
whole engine runs on our data. At monthly frequency, window args (`p`) are months.

> ⚠️ QuantaAlpha substitutes `$columns` with naive `str.replace(col[1:], ...)`,
> which corrupts overlapping names (`$me` ⊂ `$be_me`, `$at` ⊂ `$at_turnover`).
> Our `sp500_loader._to_python` does a **word-boundary, single-pass** substitution
> instead. Reused unchanged: `parse_symbol`, `parse_expression`, `function_lib`.

## Data sources (WRDS)
| Output | From |
|---|---|
| `data/sp500_membership.parquet` | `CRSP/Index - Version 2/S&P 500 Index Constituents.zip` (`MbrStartDt`/`MbrEndDt` = point-in-time add/drop) |
| `data/sp500_monthly.parquet` | `kelly_us_sample.parquet` (JKP/Kelly monthly chars) filtered to S&P 500 membership |

## Pipeline
```
python adapter/build_sp500_membership.py   # -> data/sp500_membership.parquet (2,081 spells)
python adapter/build_monthly_panel.py      # -> data/sp500_monthly.parquet   (291,944 rows, 30 $-feats, 594 months)
cd adapter && python smoke_test.py         # IC/ICIR of canonical factors (signs match literature)
```

## API for the mining loop
```python
from sp500_loader import load_features, load_labels, compute_factor, available_fields
from evaluate_ic   import summary           # RankIC / ICIR / IC_t / long-short

summary("RANK($gp_at) + RANK($be_me) - RANK($ivol_ff3_21d)")
```
`load_features()` is the drop-in for `get_qlib_stock_data()`.
`summary()['ICIR']`/`['IC']` are the RankIC feedback QuantaAlpha evolves on.

## Available `$` fields (mineable by the LLM)
price/size: `$close $me $return $turnover_126d`
momentum:   `$ret_12_1 $ret_6_1 $ret_12_7`
value:      `$be_me $bev_mev $sale_me $ni_me $at_me $eqnpo_12m`
quality:    `$gp_at $ni_be $niq_at $at_turnover $f_score`
investment: `$inv_gr1a $capx_gr1 $sale_gr1 $at_gr1 $chcsho_12m`
risk/other: `$ivol_ff3_21d $beta_60m $age $ff49 $crsp_exchcd $eqnetis_at $dbnetis_at`
label:      `ret_exc_lead1m` (next-month excess return)

## Remaining to run full LLM mining
1. `cp configs/.env.example .env`, set `OPENAI_API_KEY` / `OPENAI_BASE_URL` / model names.
2. Install QuantaAlpha deps (and either install qlib or stub the qlib calls in
   `eva_utils.py` since we bypass qlib for data).
3. `import patch_quantaalpha` before launching so the loader returns our panel.

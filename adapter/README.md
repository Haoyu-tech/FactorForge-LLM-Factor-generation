# Monthly Equity Factor Adapter

[Project overview](../README.md) · [Reproduction guide](../docs/REPRODUCIBILITY.md)

Adapt QuantaAlpha's expression grammar and operators to a WRDS-derived monthly S&P 500 panel.

## Design

| Layer | Convention |
|---|---|
| Panel index | `(datetime, instrument)` |
| Cross-sectional operators | Group by `datetime` |
| Time-series operators | Group by `instrument` |
| Window units | Months |
| Target | `ret_exc_lead1m`, next-month excess return |

The loader uses a word-boundary, single-pass substitution for dollar-prefixed fields to avoid collisions between overlapping names such as `$me` and `$be_me`.

## Prerequisites

The compatible `QuantaAlpha/quantaalpha/factors/coder/` source, external research inputs and configured monthly panels are required. QuantaAlpha is not bundled in the checkout. Record the upstream commit and environment used.

## Panel preparation

Run from the repository root and choose the intended panel workflow:

```powershell
python adapter/build_sp500_membership.py
python adapter/build_sp500_monthly_full.py
python adapter/build_sp500_monthly_kelly.py
```

The earlier `build_monthly_panel.py` route is also present. Match your configured dataset and field pool to the evaluation experiment; different panel variants are not interchangeable.

## Evaluate a known expression

```powershell
python adapter/evaluate_ic.py '$ret_12_1'
```

From the adapter directory, the programmatic interface includes:

```python
from sp500_loader import available_fields, compute_factor, load_features, load_labels
from evaluate_ic import summary

fields = available_fields()
metrics = summary("RANK($gp_at) + RANK($be_me) - RANK($ivol_ff3_21d)")
```

Use `available_fields()` as the authority for the configured panel's mineable columns.

## Data families

Price/size, momentum, value, profitability/quality, investment and risk fields are available depending on the panel variant. Keep identifier columns separate from candidate-factor inputs and retain the point-in-time membership definition.

## Live generation

Live candidate mining additionally needs the configured provider credentials and adapter integration. Stored-expression evaluation can be performed independently once data and parser dependencies are restored. Keep credentials outside version control.

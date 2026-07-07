# cashprof_taccruals_disc

```mermaid
flowchart TD
  H["Economic hypothesis: Cash profitability with low total accruals and disciplined issuance = high-quality real earnings."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$cop_at"] --> T
  F2["$eqnetis_at"] --> T
  F3["$taccruals_at"] --> T
  O1["RANK"] --> T
  O2["SUBTRACT"] --> T
  T --> E["Expression: RANK($cop_at) - RANK($taccruals_at) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0208, IC_t=+5.82, LS_SR=+0.89"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$cop_at, $eqnetis_at, $taccruals_at`
- **Operators:** `RANK, SUBTRACT`
- **Expression:** `RANK($cop_at) - RANK($taccruals_at) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0208, IC_t=+5.82, LS_SR=+0.89
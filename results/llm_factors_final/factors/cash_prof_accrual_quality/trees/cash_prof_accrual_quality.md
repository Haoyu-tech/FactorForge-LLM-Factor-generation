# cash_prof_accrual_quality

```mermaid
flowchart TD
  H["Economic hypothesis: Ball et al. (2016): cash-based operating profitability predicts returns and subsumes accruals; Sloan (1996): high operating accruals signal low earnings quality. Long real (cash-backed) profitability with low accruals and disciplined equity issuance."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$cop_at"] --> T
  F2["$eqnetis_at"] --> T
  F3["$oaccruals_at"] --> T
  O1["RANK"] --> T
  O2["SUBTRACT"] --> T
  T --> E["Expression: RANK($cop_at) - RANK($oaccruals_at) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0224, IC_t=+6.40, LS_SR=+0.98"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$cop_at, $eqnetis_at, $oaccruals_at`
- **Operators:** `RANK, SUBTRACT`
- **Expression:** `RANK($cop_at) - RANK($oaccruals_at) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0224, IC_t=+6.40, LS_SR=+0.98
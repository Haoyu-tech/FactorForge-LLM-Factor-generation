# mispr_x_cashprof

```mermaid
flowchart TD
  H["Economic hypothesis: Multiplicative: the mispricing-management signal should matter more when backed by strong cash profitability (real earnings, not accrual illusion); disciplined equity issuance."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$cop_at"] --> T
  F2["$eqnetis_at"] --> T
  F3["$mispricing_mgmt"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($mispricing_mgmt) * ZSCORE($cop_at)) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0097, IC_t=+3.16, LS_SR=+0.32"]
```

- **Family:** `llm`
- **Structure:** multiplicative interaction
- **Fields:** `$cop_at, $eqnetis_at, $mispricing_mgmt`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($mispricing_mgmt) * ZSCORE($cop_at)) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0097, IC_t=+3.16, LS_SR=+0.32
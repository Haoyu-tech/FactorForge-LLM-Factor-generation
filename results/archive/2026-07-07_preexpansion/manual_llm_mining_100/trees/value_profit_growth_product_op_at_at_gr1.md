# value_profit_growth_product_op_at_at_gr1

```mermaid
flowchart TD
  H["Economic hypothesis: Value works better when paired with profitability, low growth pressure, and low equity issuance."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$be_me"] --> T
  F3["$eqnetis_at"] --> T
  F4["$op_at"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK((ZSCORE($be_me) * ZSCORE($op_at))) - RANK($at_gr1) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0153, IC_t=+4.36, LS_SR=+0.58"]
```

- **Family:** `profitability_efficiency_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$at_gr1, $be_me, $eqnetis_at, $op_at`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK((ZSCORE($be_me) * ZSCORE($op_at))) - RANK($at_gr1) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0153, IC_t=+4.36, LS_SR=+0.58
# value_profit_growth_product_op_at_sale_gr1

```mermaid
flowchart TD
  H["Economic hypothesis: Value works better when paired with profitability, low growth pressure, and low equity issuance."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$op_at"] --> T
  F4["$sale_gr1"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK((ZSCORE($be_me) * ZSCORE($op_at))) - RANK($sale_gr1) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0132, IC_t=+3.49, LS_SR=+0.56"]
```

- **Family:** `profitability_efficiency_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $eqnetis_at, $op_at, $sale_gr1`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK((ZSCORE($be_me) * ZSCORE($op_at))) - RANK($sale_gr1) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0132, IC_t=+3.49, LS_SR=+0.56
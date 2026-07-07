# value_profit_growth_product_ni_be_sale_gr1

```mermaid
flowchart TD
  H["Economic hypothesis: Value works better when paired with profitability, low growth pressure, and low equity issuance."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$ni_be"] --> T
  F4["$sale_gr1"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK((ZSCORE($be_me) * ZSCORE($ni_be))) - RANK($sale_gr1) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0135, IC_t=+3.37, LS_SR=+0.53"]
```

- **Family:** `profitability_efficiency_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $eqnetis_at, $ni_be, $sale_gr1`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK((ZSCORE($be_me) * ZSCORE($ni_be))) - RANK($sale_gr1) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0135, IC_t=+3.37, LS_SR=+0.53
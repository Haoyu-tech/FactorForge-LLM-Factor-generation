# value_profit_growth_product_qmj_prof_noa_at

```mermaid
flowchart TD
  H["Economic hypothesis: Value works better when paired with profitability, low growth pressure, and low equity issuance."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$noa_at"] --> T
  F4["$qmj_prof"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK((ZSCORE($be_me) * ZSCORE($qmj_prof))) - RANK($noa_at) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0186, IC_t=+5.76, LS_SR=+0.84"]
```

- **Family:** `profitability_efficiency_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $eqnetis_at, $noa_at, $qmj_prof`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK((ZSCORE($be_me) * ZSCORE($qmj_prof))) - RANK($noa_at) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0186, IC_t=+5.76, LS_SR=+0.84
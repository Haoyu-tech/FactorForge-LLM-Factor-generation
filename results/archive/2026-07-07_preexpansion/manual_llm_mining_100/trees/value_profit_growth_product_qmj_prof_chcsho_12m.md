# value_profit_growth_product_qmj_prof_chcsho_12m

```mermaid
flowchart TD
  H["Economic hypothesis: Value works better when paired with profitability, low growth pressure, and low equity issuance."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$chcsho_12m"] --> T
  F3["$eqnetis_at"] --> T
  F4["$qmj_prof"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK((ZSCORE($be_me) * ZSCORE($qmj_prof))) - RANK($chcsho_12m) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0155, IC_t=+4.54, LS_SR=+0.55"]
```

- **Family:** `profitability_efficiency_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $chcsho_12m, $eqnetis_at, $qmj_prof`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK((ZSCORE($be_me) * ZSCORE($qmj_prof))) - RANK($chcsho_12m) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0155, IC_t=+4.54, LS_SR=+0.55
# interaction_value_prof

```mermaid
flowchart TD
  H["Economic hypothesis: The product term asks whether two economically distinct signals reinforce each other rather than merely add linearly."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$op_at"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($be_me) * ZSCORE($op_at)) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0135, IC_t=+4.14, LS_SR=+0.47"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $eqnetis_at, $op_at`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($be_me) * ZSCORE($op_at)) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0135, IC_t=+4.14, LS_SR=+0.47
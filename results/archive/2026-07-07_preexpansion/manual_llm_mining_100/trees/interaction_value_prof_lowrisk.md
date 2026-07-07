# interaction_value_prof_lowrisk

```mermaid
flowchart TD
  H["Economic hypothesis: The interaction is combined with a low-risk filter to reduce fragile anomaly exposure."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$ivol_ff3_21d"] --> T
  F4["$op_at"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($be_me) * ZSCORE($op_at)) - RANK($eqnetis_at) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0197, IC_t=+4.33, LS_SR=+0.22"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $eqnetis_at, $ivol_ff3_21d, $op_at`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($be_me) * ZSCORE($op_at)) - RANK($eqnetis_at) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0197, IC_t=+4.33, LS_SR=+0.22
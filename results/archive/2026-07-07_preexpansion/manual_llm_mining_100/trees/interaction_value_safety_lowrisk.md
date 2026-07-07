# interaction_value_safety_lowrisk

```mermaid
flowchart TD
  H["Economic hypothesis: The interaction is combined with a low-risk filter to reduce fragile anomaly exposure."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$beta_60m"] --> T
  F3["$ivol_ff3_21d"] --> T
  F4["$qmj_safety"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($be_me) * ZSCORE($qmj_safety)) - RANK($beta_60m) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0175, IC_t=+2.37, LS_SR=-0.03"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $beta_60m, $ivol_ff3_21d, $qmj_safety`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($be_me) * ZSCORE($qmj_safety)) - RANK($beta_60m) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0175, IC_t=+2.37, LS_SR=-0.03
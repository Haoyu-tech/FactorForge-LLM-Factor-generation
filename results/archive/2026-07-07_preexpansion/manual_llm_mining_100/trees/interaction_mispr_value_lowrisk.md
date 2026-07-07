# interaction_mispr_value_lowrisk

```mermaid
flowchart TD
  H["Economic hypothesis: The interaction is combined with a low-risk filter to reduce fragile anomaly exposure."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$be_me"] --> T
  F3["$ivol_ff3_21d"] --> T
  F4["$mispricing_perf"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($mispricing_perf) * ZSCORE($be_me)) - RANK($at_gr1) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0117, IC_t=+2.65, LS_SR=+0.14"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$at_gr1, $be_me, $ivol_ff3_21d, $mispricing_perf`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($mispricing_perf) * ZSCORE($be_me)) - RANK($at_gr1) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0117, IC_t=+2.65, LS_SR=+0.14
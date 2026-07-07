# interaction_mom_quality_lowrisk

```mermaid
flowchart TD
  H["Economic hypothesis: The interaction is combined with a low-risk filter to reduce fragile anomaly exposure."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$ivol_ff3_21d"] --> T
  F2["$qmj_prof"] --> T
  F3["$ret_12_1"] --> T
  F4["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($ret_12_1) * ZSCORE($qmj_prof)) - RANK($ret_1_0) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0242, IC_t=+5.57, LS_SR=+0.33"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$ivol_ff3_21d, $qmj_prof, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($ret_12_1) * ZSCORE($qmj_prof)) - RANK($ret_1_0) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0242, IC_t=+5.57, LS_SR=+0.33
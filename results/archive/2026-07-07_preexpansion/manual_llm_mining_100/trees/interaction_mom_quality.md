# interaction_mom_quality

```mermaid
flowchart TD
  H["Economic hypothesis: The product term asks whether two economically distinct signals reinforce each other rather than merely add linearly."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$qmj_prof"] --> T
  F2["$ret_12_1"] --> T
  F3["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($ret_12_1) * ZSCORE($qmj_prof)) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0171, IC_t=+3.76, LS_SR=+0.40"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$qmj_prof, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($ret_12_1) * ZSCORE($qmj_prof)) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0171, IC_t=+3.76, LS_SR=+0.40
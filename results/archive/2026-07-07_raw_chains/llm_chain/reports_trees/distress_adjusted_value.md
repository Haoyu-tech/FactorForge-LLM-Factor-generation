# distress_adjusted_value

```mermaid
flowchart TD
  H["Economic hypothesis: Value works better among financially healthy firms (Piotroski 2000; Campbell-Hilscher-Szilagyi distress): cheap plus high Altman-Z plus low idiosyncratic risk avoids the distressed value trap."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$ivol_ff3_21d"] --> T
  F3["$z_score"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($be_me) + RANK($z_score) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0203, IC_t=+4.57, LS_SR=+0.27"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$be_me, $ivol_ff3_21d, $z_score`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($be_me) + RANK($z_score) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0203, IC_t=+4.57, LS_SR=+0.27
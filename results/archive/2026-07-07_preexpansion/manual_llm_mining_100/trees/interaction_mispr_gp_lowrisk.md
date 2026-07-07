# interaction_mispr_gp_lowrisk

```mermaid
flowchart TD
  H["Economic hypothesis: The interaction is combined with a low-risk filter to reduce fragile anomaly exposure."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$gp_at"] --> T
  F3["$ivol_ff3_21d"] --> T
  F4["$mispricing_mgmt"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($mispricing_mgmt) * ZSCORE($gp_at)) - RANK($eqnetis_at) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0189, IC_t=+4.02, LS_SR=+0.15"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$eqnetis_at, $gp_at, $ivol_ff3_21d, $mispricing_mgmt`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($mispricing_mgmt) * ZSCORE($gp_at)) - RANK($eqnetis_at) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0189, IC_t=+4.02, LS_SR=+0.15
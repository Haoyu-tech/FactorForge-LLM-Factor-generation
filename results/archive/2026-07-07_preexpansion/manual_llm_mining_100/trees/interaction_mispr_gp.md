# interaction_mispr_gp

```mermaid
flowchart TD
  H["Economic hypothesis: The product term asks whether two economically distinct signals reinforce each other rather than merely add linearly."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$gp_at"] --> T
  F3["$mispricing_mgmt"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($mispricing_mgmt) * ZSCORE($gp_at)) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0103, IC_t=+3.38, LS_SR=+0.41"]
```

- **Family:** `multiplicative_interaction`
- **Structure:** multiplicative interaction
- **Fields:** `$eqnetis_at, $gp_at, $mispricing_mgmt`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($mispricing_mgmt) * ZSCORE($gp_at)) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0103, IC_t=+3.38, LS_SR=+0.41
# mispr_fin_disc_op

```mermaid
flowchart TD
  H["Economic hypothesis: Mispricing reversal with financing and investment discipline, reinforced by operating profitability."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$eqnetis_at"] --> T
  F3["$mispricing_mgmt"] --> T
  F4["$mispricing_perf"] --> T
  F5["$op_at"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1) + RANK($op_at)"]
  E --> M["Metrics: IC=+0.0286, IC_t=+7.55, LS_SR=+0.85"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$at_gr1, $eqnetis_at, $mispricing_mgmt, $mispricing_perf, $op_at`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1) + RANK($op_at)`
- **Metrics:** IC=+0.0286, IC_t=+7.55, LS_SR=+0.85
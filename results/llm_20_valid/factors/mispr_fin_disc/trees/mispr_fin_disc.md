# mispr_fin_disc

```mermaid
flowchart TD
  H["Economic hypothesis: Stambaugh-Yuan mispricing reverses more strongly among firms with restrained equity issuance and asset growth (q-theory discipline)."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$eqnetis_at"] --> T
  F3["$mispricing_mgmt"] --> T
  F4["$mispricing_perf"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1)"]
  E --> M["Metrics: IC=+0.0277, IC_t=+7.89, LS_SR=+0.89"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$at_gr1, $eqnetis_at, $mispricing_mgmt, $mispricing_perf`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1)`
- **Metrics:** IC=+0.0277, IC_t=+7.89, LS_SR=+0.89
# mispr_fin_disc_quality

```mermaid
flowchart TD
  H["Economic hypothesis: Mispricing reversal is cleaner when supported by real gross profitability alongside financing and investment discipline."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$eqnetis_at"] --> T
  F3["$gp_at"] --> T
  F4["$mispricing_mgmt"] --> T
  F5["$mispricing_perf"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1) + RANK($gp_at)"]
  E --> M["Metrics: IC=+0.0267, IC_t=+6.93, LS_SR=+0.82"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$at_gr1, $eqnetis_at, $gp_at, $mispricing_mgmt, $mispricing_perf`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($at_gr1) + RANK($gp_at)`
- **Metrics:** IC=+0.0267, IC_t=+6.93, LS_SR=+0.82
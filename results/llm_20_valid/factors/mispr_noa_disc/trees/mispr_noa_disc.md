# mispr_noa_disc

```mermaid
flowchart TD
  H["Economic hypothesis: Mispricing combined with low net operating assets (Hirshleifer bloat) and low issuance targets over-accruing over-valued firms."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$mispricing_mgmt"] --> T
  F3["$mispricing_perf"] --> T
  F4["$noa_at"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($noa_at)"]
  E --> M["Metrics: IC=+0.0296, IC_t=+8.31, LS_SR=+0.88"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$eqnetis_at, $mispricing_mgmt, $mispricing_perf, $noa_at`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($noa_at)`
- **Metrics:** IC=+0.0296, IC_t=+8.31, LS_SR=+0.88
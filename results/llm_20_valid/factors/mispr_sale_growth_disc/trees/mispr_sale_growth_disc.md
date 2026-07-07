# mispr_sale_growth_disc

```mermaid
flowchart TD
  H["Economic hypothesis: Mispricing combined with low issuance and restrained sales growth (revenue-side overexpansion)."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$mispricing_mgmt"] --> T
  F3["$mispricing_perf"] --> T
  F4["$sale_gr1"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($sale_gr1)"]
  E --> M["Metrics: IC=+0.0270, IC_t=+7.15, LS_SR=+0.82"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$eqnetis_at, $mispricing_mgmt, $mispricing_perf, $sale_gr1`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) - RANK($eqnetis_at) - RANK($sale_gr1)`
- **Metrics:** IC=+0.0270, IC_t=+7.15, LS_SR=+0.82
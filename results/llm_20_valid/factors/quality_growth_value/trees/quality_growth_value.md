# quality_growth_value

```mermaid
flowchart TD
  H["Economic hypothesis: Profitability quality and ROE tilted to cheap sales-to-price and low bloat."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$ni_be"] --> T
  F2["$noa_at"] --> T
  F3["$qmj_prof"] --> T
  F4["$sale_me"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($qmj_prof) + RANK($ni_be) + RANK($sale_me) - RANK($noa_at)"]
  E --> M["Metrics: IC=+0.0252, IC_t=+6.42, LS_SR=+0.75"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$ni_be, $noa_at, $qmj_prof, $sale_me`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($qmj_prof) + RANK($ni_be) + RANK($sale_me) - RANK($noa_at)`
- **Metrics:** IC=+0.0252, IC_t=+6.42, LS_SR=+0.75
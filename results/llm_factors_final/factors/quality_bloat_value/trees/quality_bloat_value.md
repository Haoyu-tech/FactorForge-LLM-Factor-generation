# quality_bloat_value

```mermaid
flowchart TD
  H["Economic hypothesis: Asness-Frazzini-Pedersen quality (profitability plus safety) tilted toward cheap sales-to-price with low net operating assets (Hirshleifer et al. bloated-balance-sheet / NOA anomaly)."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$noa_at"] --> T
  F2["$qmj_prof"] --> T
  F3["$qmj_safety"] --> T
  F4["$sale_me"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($qmj_prof) + RANK($qmj_safety) + RANK($sale_me) - RANK($noa_at)"]
  E --> M["Metrics: IC=+0.0264, IC_t=+7.16, LS_SR=+0.84"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$noa_at, $qmj_prof, $qmj_safety, $sale_me`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($qmj_prof) + RANK($qmj_safety) + RANK($sale_me) - RANK($noa_at)`
- **Metrics:** IC=+0.0264, IC_t=+7.16, LS_SR=+0.84
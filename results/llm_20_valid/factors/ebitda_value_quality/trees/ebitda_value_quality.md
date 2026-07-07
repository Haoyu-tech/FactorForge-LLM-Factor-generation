# ebitda_value_quality

```mermaid
flowchart TD
  H["Economic hypothesis: EBITDA-to-market-EV value tilted toward quality profitability, penalizing equity issuance."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$ebitda_mev"] --> T
  F2["$eqnetis_at"] --> T
  F3["$qmj_prof"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($ebitda_mev) + RANK($qmj_prof) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0297, IC_t=+7.38, LS_SR=+0.82"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$ebitda_mev, $eqnetis_at, $qmj_prof`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($ebitda_mev) + RANK($qmj_prof) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0297, IC_t=+7.38, LS_SR=+0.82
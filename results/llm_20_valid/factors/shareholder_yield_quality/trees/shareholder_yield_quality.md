# shareholder_yield_quality

```mermaid
flowchart TD
  H["Economic hypothesis: Net payout yield (Boudoukh) plus cash profitability, penalizing issuance: firms returning cash and generating real profits."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$cop_at"] --> T
  F2["$eqnetis_at"] --> T
  F3["$eqnpo_me"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($eqnpo_me) + RANK($cop_at) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0288, IC_t=+7.70, LS_SR=+0.96"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$cop_at, $eqnetis_at, $eqnpo_me`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($eqnpo_me) + RANK($cop_at) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0288, IC_t=+7.70, LS_SR=+0.96
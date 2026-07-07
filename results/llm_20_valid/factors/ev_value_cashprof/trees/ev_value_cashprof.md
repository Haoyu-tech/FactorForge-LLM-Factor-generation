# ev_value_cashprof

```mermaid
flowchart TD
  H["Economic hypothesis: Enterprise-multiple value (EBIT/book-EV) is cleaner than book-to-market for levered firms; plus cash profitability and low investment."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$cop_at"] --> T
  F3["$ebit_bev"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($ebit_bev) + RANK($cop_at) - RANK($at_gr1)"]
  E --> M["Metrics: IC=+0.0225, IC_t=+6.46, LS_SR=+0.78"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$at_gr1, $cop_at, $ebit_bev`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($ebit_bev) + RANK($cop_at) - RANK($at_gr1)`
- **Metrics:** IC=+0.0225, IC_t=+6.46, LS_SR=+0.78
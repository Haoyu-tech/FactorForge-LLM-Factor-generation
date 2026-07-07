# coa_growth_quality

```mermaid
flowchart TD
  H["Economic hypothesis: Change in current operating assets and asset growth are overinvestment signals; cash profitability offsets them."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$coa_gr1a"] --> T
  F3["$cop_at"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: -RANK($coa_gr1a) - RANK($at_gr1) + RANK($cop_at)"]
  E --> M["Metrics: IC=+0.0167, IC_t=+4.99, LS_SR=+0.93"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$at_gr1, $coa_gr1a, $cop_at`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `-RANK($coa_gr1a) - RANK($at_gr1) + RANK($cop_at)`
- **Metrics:** IC=+0.0167, IC_t=+4.99, LS_SR=+0.93
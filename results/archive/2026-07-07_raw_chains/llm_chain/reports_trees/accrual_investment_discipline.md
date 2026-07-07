# accrual_investment_discipline

```mermaid
flowchart TD
  H["Economic hypothesis: Total accruals (Richardson et al. 2005) and asset growth (Cooper et al. 2008) are overinvestment / low-quality signals; cash profitability is the real-earnings counterweight."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$cop_at"] --> T
  F3["$taccruals_at"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: -RANK($taccruals_at) - RANK($at_gr1) + RANK($cop_at)"]
  E --> M["Metrics: IC=+0.0166, IC_t=+4.77, LS_SR=+0.82"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$at_gr1, $cop_at, $taccruals_at`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `-RANK($taccruals_at) - RANK($at_gr1) + RANK($cop_at)`
- **Metrics:** IC=+0.0166, IC_t=+4.77, LS_SR=+0.82
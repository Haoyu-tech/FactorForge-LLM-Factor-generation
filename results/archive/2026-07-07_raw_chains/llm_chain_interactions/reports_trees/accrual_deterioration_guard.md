# accrual_deterioration_guard

```mermaid
flowchart TD
  H["Economic hypothesis: Time-series: a rising 12-month change in operating accruals signals deteriorating earnings quality; combined with restrained asset growth and real cash profitability."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$cop_at"] --> T
  F3["$oaccruals_at"] --> T
  O1["RANK"] --> T
  O2["DELTA"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: -RANK(DELTA($oaccruals_at, 12)) - RANK($at_gr1) + RANK($cop_at)"]
  E --> M["Metrics: IC=+0.0177, IC_t=+5.93, LS_SR=+0.89"]
```

- **Family:** `llm`
- **Structure:** time-series transform
- **Fields:** `$at_gr1, $cop_at, $oaccruals_at`
- **Operators:** `RANK, DELTA, ADD, SUBTRACT`
- **Expression:** `-RANK(DELTA($oaccruals_at, 12)) - RANK($at_gr1) + RANK($cop_at)`
- **Metrics:** IC=+0.0177, IC_t=+5.93, LS_SR=+0.89
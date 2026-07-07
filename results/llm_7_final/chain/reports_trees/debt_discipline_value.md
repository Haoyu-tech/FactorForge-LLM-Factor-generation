# debt_discipline_value

```mermaid
flowchart TD
  H["Economic hypothesis: Low debt issuance and leverage with value and cash profitability captures conservatively financed cheap firms."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$cop_at"] --> T
  F3["$dbnetis_at"] --> T
  F4["$debt_me"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: -RANK($dbnetis_at) - RANK($debt_me) + RANK($be_me) + RANK($cop_at)"]
  E --> M["Metrics: IC=+0.0165, IC_t=+4.98, LS_SR=+0.81"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$be_me, $cop_at, $dbnetis_at, $debt_me`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `-RANK($dbnetis_at) - RANK($debt_me) + RANK($be_me) + RANK($cop_at)`
- **Metrics:** IC=+0.0165, IC_t=+4.98, LS_SR=+0.81
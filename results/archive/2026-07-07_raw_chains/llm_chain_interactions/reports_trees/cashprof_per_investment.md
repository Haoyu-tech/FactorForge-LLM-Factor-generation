# cashprof_per_investment

```mermaid
flowchart TD
  H["Economic hypothesis: Ratio: cash profitability per unit of asset growth isolates efficient profit generation without empire-building; low equity issuance."] --> S["Structure: ratio / risk scaling"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$cop_at"] --> T
  F3["$eqnetis_at"] --> T
  O1["RANK"] --> T
  O2["ABS"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK($cop_at / (ABS($at_gr1) + 1)) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0248, IC_t=+6.62, LS_SR=+0.82"]
```

- **Family:** `llm`
- **Structure:** ratio / risk scaling
- **Fields:** `$at_gr1, $cop_at, $eqnetis_at`
- **Operators:** `RANK, ABS, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK($cop_at / (ABS($at_gr1) + 1)) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0248, IC_t=+6.62, LS_SR=+0.82
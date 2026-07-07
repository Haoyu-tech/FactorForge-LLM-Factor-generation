# profit_to_growth_value_op_at_noa_at

```mermaid
flowchart TD
  H["Economic hypothesis: Profitability scaled by growth separates efficient value firms from firms expanding assets or shares aggressively."] --> S["Structure: ratio / risk scaling"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$noa_at"] --> T
  F4["$op_at"] --> T
  O1["RANK"] --> T
  O2["ABS"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK($op_at / (ABS($noa_at) + 1)) + RANK($be_me) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0272, IC_t=+6.74, LS_SR=+0.95"]
```

- **Family:** `profitability_efficiency_ratio`
- **Structure:** ratio / risk scaling
- **Fields:** `$be_me, $eqnetis_at, $noa_at, $op_at`
- **Operators:** `RANK, ABS, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK($op_at / (ABS($noa_at) + 1)) + RANK($be_me) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0272, IC_t=+6.74, LS_SR=+0.95
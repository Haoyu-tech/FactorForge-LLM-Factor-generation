# profit_to_growth_value_ni_be_chcsho_12m

```mermaid
flowchart TD
  H["Economic hypothesis: Profitability scaled by growth separates efficient value firms from firms expanding assets or shares aggressively."] --> S["Structure: ratio / risk scaling"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$chcsho_12m"] --> T
  F3["$eqnetis_at"] --> T
  F4["$ni_be"] --> T
  O1["RANK"] --> T
  O2["ABS"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK($ni_be / (ABS($chcsho_12m) + 1)) + RANK($be_me) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0285, IC_t=+6.77, LS_SR=+0.65"]
```

- **Family:** `profitability_efficiency_ratio`
- **Structure:** ratio / risk scaling
- **Fields:** `$be_me, $chcsho_12m, $eqnetis_at, $ni_be`
- **Operators:** `RANK, ABS, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK($ni_be / (ABS($chcsho_12m) + 1)) + RANK($be_me) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0285, IC_t=+6.77, LS_SR=+0.65
# profit_to_growth_value_gp_at_sale_gr1

```mermaid
flowchart TD
  H["Economic hypothesis: Profitability scaled by growth separates efficient value firms from firms expanding assets or shares aggressively."] --> S["Structure: ratio / risk scaling"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$gp_at"] --> T
  F4["$sale_gr1"] --> T
  O1["RANK"] --> T
  O2["ABS"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK($gp_at / (ABS($sale_gr1) + 1)) + RANK($be_me) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0243, IC_t=+5.62, LS_SR=+0.72"]
```

- **Family:** `profitability_efficiency_ratio`
- **Structure:** ratio / risk scaling
- **Fields:** `$be_me, $eqnetis_at, $gp_at, $sale_gr1`
- **Operators:** `RANK, ABS, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK($gp_at / (ABS($sale_gr1) + 1)) + RANK($be_me) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0243, IC_t=+5.62, LS_SR=+0.72
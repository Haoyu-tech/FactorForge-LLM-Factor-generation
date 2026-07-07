# profit_to_growth_value_qmj_prof_at_gr1

```mermaid
flowchart TD
  H["Economic hypothesis: Profitability scaled by growth separates efficient value firms from firms expanding assets or shares aggressively."] --> S["Structure: ratio / risk scaling"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$be_me"] --> T
  F3["$eqnetis_at"] --> T
  F4["$qmj_prof"] --> T
  O1["RANK"] --> T
  O2["ABS"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK($qmj_prof / (ABS($at_gr1) + 1)) + RANK($be_me) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0277, IC_t=+6.97, LS_SR=+0.82"]
```

- **Family:** `profitability_efficiency_ratio`
- **Structure:** ratio / risk scaling
- **Fields:** `$at_gr1, $be_me, $eqnetis_at, $qmj_prof`
- **Operators:** `RANK, ABS, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK($qmj_prof / (ABS($at_gr1) + 1)) + RANK($be_me) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0277, IC_t=+6.97, LS_SR=+0.82
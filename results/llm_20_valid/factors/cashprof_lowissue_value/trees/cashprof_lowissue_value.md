# cashprof_lowissue_value

```mermaid
flowchart TD
  H["Economic hypothesis: Cheap, cash-profitable firms that neither issue equity nor grow share count combine value, quality, and financing discipline."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$chcsho_12m"] --> T
  F3["$cop_at"] --> T
  F4["$eqnetis_at"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($cop_at) + RANK($be_me) - RANK($eqnetis_at) - RANK($chcsho_12m)"]
  E --> M["Metrics: IC=+0.0261, IC_t=+6.65, LS_SR=+0.88"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$be_me, $chcsho_12m, $cop_at, $eqnetis_at`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($cop_at) + RANK($be_me) - RANK($eqnetis_at) - RANK($chcsho_12m)`
- **Metrics:** IC=+0.0261, IC_t=+6.65, LS_SR=+0.88
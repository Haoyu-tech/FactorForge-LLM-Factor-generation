# riskadj_momentum_disc

```mermaid
flowchart TD
  H["Economic hypothesis: Ratio: risk-adjusted momentum (information-ratio style) — momentum per unit realized volatility — combined with financing discipline."] --> S["Structure: ratio / risk scaling"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$ret_12_1"] --> T
  F3["$ret_1_0"] --> T
  F4["$rvol_21d"] --> T
  O1["RANK"] --> T
  O2["DIVIDE"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(($ret_12_1 - $ret_1_0) / ($rvol_21d + 1)) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0332, IC_t=+6.14, LS_SR=+0.58"]
```

- **Family:** `llm`
- **Structure:** ratio / risk scaling
- **Fields:** `$eqnetis_at, $ret_12_1, $ret_1_0, $rvol_21d`
- **Operators:** `RANK, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($ret_12_1 - $ret_1_0) / ($rvol_21d + 1)) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0332, IC_t=+6.14, LS_SR=+0.58
# risk_scaled_value_quality_fin_12

```mermaid
flowchart TD
  H["Economic hypothesis: Risk-scaled signals are strengthened by low idiosyncratic risk and low equity issuance."] --> S["Structure: ratio / risk scaling, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$gp_at"] --> T
  F4["$ivol_ff3_21d"] --> T
  F5["$return"] --> T
  O1["RANK"] --> T
  O2["TS_STD"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK(($be_me + $gp_at) / TS_STD($return, 12)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0286, IC_t=+4.65, LS_SR=+0.28"]
```

- **Family:** `risk_scaled_ratio`
- **Structure:** ratio / risk scaling, time-series transform
- **Fields:** `$be_me, $eqnetis_at, $gp_at, $ivol_ff3_21d, $return`
- **Operators:** `RANK, TS_STD, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($be_me + $gp_at) / TS_STD($return, 12)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0286, IC_t=+4.65, LS_SR=+0.28
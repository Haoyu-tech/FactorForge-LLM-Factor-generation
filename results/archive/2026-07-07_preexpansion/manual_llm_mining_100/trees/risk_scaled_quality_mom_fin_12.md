# risk_scaled_quality_mom_fin_12

```mermaid
flowchart TD
  H["Economic hypothesis: Risk-scaled signals are strengthened by low idiosyncratic risk and low equity issuance."] --> S["Structure: ratio / risk scaling, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$gp_at"] --> T
  F3["$ivol_ff3_21d"] --> T
  F4["$ret_12_1"] --> T
  F5["$ret_1_0"] --> T
  F6["$return"] --> T
  O1["RANK"] --> T
  O2["TS_STD"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK(($gp_at + $ret_12_1 - $ret_1_0) / TS_STD($return, 12)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0333, IC_t=+5.32, LS_SR=+0.32"]
```

- **Family:** `risk_scaled_ratio`
- **Structure:** ratio / risk scaling, time-series transform
- **Fields:** `$eqnetis_at, $gp_at, $ivol_ff3_21d, $ret_12_1, $ret_1_0, $return`
- **Operators:** `RANK, TS_STD, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($gp_at + $ret_12_1 - $ret_1_0) / TS_STD($return, 12)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0333, IC_t=+5.32, LS_SR=+0.32
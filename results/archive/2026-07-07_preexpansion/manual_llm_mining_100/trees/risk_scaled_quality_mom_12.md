# risk_scaled_quality_mom_12

```mermaid
flowchart TD
  H["Economic hypothesis: Signals scaled by realized volatility should reduce noisy high-risk exposure."] --> S["Structure: ratio / risk scaling, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$gp_at"] --> T
  F2["$ivol_ff3_21d"] --> T
  F3["$ret_12_1"] --> T
  F4["$ret_1_0"] --> T
  F5["$return"] --> T
  O1["RANK"] --> T
  O2["TS_STD"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK(($gp_at + $ret_12_1 - $ret_1_0) / TS_STD($return, 12)) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0289, IC_t=+4.13, LS_SR=+0.15"]
```

- **Family:** `risk_scaled_ratio`
- **Structure:** ratio / risk scaling, time-series transform
- **Fields:** `$gp_at, $ivol_ff3_21d, $ret_12_1, $ret_1_0, $return`
- **Operators:** `RANK, TS_STD, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($gp_at + $ret_12_1 - $ret_1_0) / TS_STD($return, 12)) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0289, IC_t=+4.13, LS_SR=+0.15
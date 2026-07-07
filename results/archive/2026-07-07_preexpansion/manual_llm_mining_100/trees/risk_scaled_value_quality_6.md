# risk_scaled_value_quality_6

```mermaid
flowchart TD
  H["Economic hypothesis: Signals scaled by realized volatility should reduce noisy high-risk exposure."] --> S["Structure: ratio / risk scaling, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$gp_at"] --> T
  F3["$ivol_ff3_21d"] --> T
  F4["$return"] --> T
  O1["RANK"] --> T
  O2["TS_STD"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK(($be_me + $gp_at) / TS_STD($return, 6)) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0228, IC_t=+3.55, LS_SR=+0.13"]
```

- **Family:** `risk_scaled_ratio`
- **Structure:** ratio / risk scaling, time-series transform
- **Fields:** `$be_me, $gp_at, $ivol_ff3_21d, $return`
- **Operators:** `RANK, TS_STD, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($be_me + $gp_at) / TS_STD($return, 6)) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0228, IC_t=+3.55, LS_SR=+0.13
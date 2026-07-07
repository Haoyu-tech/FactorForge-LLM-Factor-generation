# risk_scaled_mispricing_6

```mermaid
flowchart TD
  H["Economic hypothesis: Signals scaled by realized volatility should reduce noisy high-risk exposure."] --> S["Structure: ratio / risk scaling, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$ivol_ff3_21d"] --> T
  F2["$mispricing_mgmt"] --> T
  F3["$mispricing_perf"] --> T
  F4["$return"] --> T
  O1["RANK"] --> T
  O2["TS_STD"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK(($mispricing_perf + $mispricing_mgmt) / TS_STD($return, 6)) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0239, IC_t=+3.38, LS_SR=+0.05"]
```

- **Family:** `risk_scaled_ratio`
- **Structure:** ratio / risk scaling, time-series transform
- **Fields:** `$ivol_ff3_21d, $mispricing_mgmt, $mispricing_perf, $return`
- **Operators:** `RANK, TS_STD, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($mispricing_perf + $mispricing_mgmt) / TS_STD($return, 6)) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0239, IC_t=+3.38, LS_SR=+0.05
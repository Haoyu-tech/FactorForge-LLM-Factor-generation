# risk_scaled_mispricing_fin_24

```mermaid
flowchart TD
  H["Economic hypothesis: Risk-scaled signals are strengthened by low idiosyncratic risk and low equity issuance."] --> S["Structure: ratio / risk scaling, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$ivol_ff3_21d"] --> T
  F3["$mispricing_mgmt"] --> T
  F4["$mispricing_perf"] --> T
  F5["$return"] --> T
  O1["RANK"] --> T
  O2["TS_STD"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK(($mispricing_perf + $mispricing_mgmt) / TS_STD($return, 24)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0290, IC_t=+4.32, LS_SR=+0.20"]
```

- **Family:** `risk_scaled_ratio`
- **Structure:** ratio / risk scaling, time-series transform
- **Fields:** `$eqnetis_at, $ivol_ff3_21d, $mispricing_mgmt, $mispricing_perf, $return`
- **Operators:** `RANK, TS_STD, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($mispricing_perf + $mispricing_mgmt) / TS_STD($return, 24)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0290, IC_t=+4.32, LS_SR=+0.20
# risk_scaled_value_mom_fin_24

```mermaid
flowchart TD
  H["Economic hypothesis: Risk-scaled signals are strengthened by low idiosyncratic risk and low equity issuance."] --> S["Structure: ratio / risk scaling, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$ivol_ff3_21d"] --> T
  F4["$ret_12_1"] --> T
  F5["$ret_1_0"] --> T
  F6["$return"] --> T
  O1["RANK"] --> T
  O2["TS_STD"] --> T
  O3["DIVIDE"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: RANK(($be_me + $ret_12_1 - $ret_1_0) / TS_STD($return, 24)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0339, IC_t=+5.69, LS_SR=+0.41"]
```

- **Family:** `risk_scaled_ratio`
- **Structure:** ratio / risk scaling, time-series transform
- **Fields:** `$be_me, $eqnetis_at, $ivol_ff3_21d, $ret_12_1, $ret_1_0, $return`
- **Operators:** `RANK, TS_STD, DIVIDE, ADD, SUBTRACT`
- **Expression:** `RANK(($be_me + $ret_12_1 - $ret_1_0) / TS_STD($return, 24)) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0339, IC_t=+5.69, LS_SR=+0.41
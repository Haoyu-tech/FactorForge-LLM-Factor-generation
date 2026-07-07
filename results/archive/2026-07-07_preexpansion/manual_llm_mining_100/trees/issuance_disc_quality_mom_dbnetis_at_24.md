# issuance_disc_quality_mom_dbnetis_at_24

```mermaid
flowchart TD
  H["Economic hypothesis: Low financing, profitability, and momentum combine capital discipline with underreaction."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$dbnetis_at"] --> T
  F2["$op_at"] --> T
  F3["$ret_12_1"] --> T
  F4["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["TS_MEAN"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: -RANK(TS_MEAN($dbnetis_at, 24)) + RANK($ret_12_1) - RANK($ret_1_0) + RANK($op_at)"]
  E --> M["Metrics: IC=+0.0257, IC_t=+5.19, LS_SR=+0.45"]
```

- **Family:** `issuance_momentum_ts`
- **Structure:** time-series transform
- **Fields:** `$dbnetis_at, $op_at, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, TS_MEAN, ADD, SUBTRACT`
- **Expression:** `-RANK(TS_MEAN($dbnetis_at, 24)) + RANK($ret_12_1) - RANK($ret_1_0) + RANK($op_at)`
- **Metrics:** IC=+0.0257, IC_t=+5.19, LS_SR=+0.45
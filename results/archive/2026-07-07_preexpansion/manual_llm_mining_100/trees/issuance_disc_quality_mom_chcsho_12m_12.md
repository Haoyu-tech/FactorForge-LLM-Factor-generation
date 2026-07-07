# issuance_disc_quality_mom_chcsho_12m_12

```mermaid
flowchart TD
  H["Economic hypothesis: Low financing, profitability, and momentum combine capital discipline with underreaction."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$chcsho_12m"] --> T
  F2["$op_at"] --> T
  F3["$ret_12_1"] --> T
  F4["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["TS_MEAN"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: -RANK(TS_MEAN($chcsho_12m, 12)) + RANK($ret_12_1) - RANK($ret_1_0) + RANK($op_at)"]
  E --> M["Metrics: IC=+0.0347, IC_t=+7.10, LS_SR=+0.66"]
```

- **Family:** `issuance_momentum_ts`
- **Structure:** time-series transform
- **Fields:** `$chcsho_12m, $op_at, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, TS_MEAN, ADD, SUBTRACT`
- **Expression:** `-RANK(TS_MEAN($chcsho_12m, 12)) + RANK($ret_12_1) - RANK($ret_1_0) + RANK($op_at)`
- **Metrics:** IC=+0.0347, IC_t=+7.10, LS_SR=+0.66
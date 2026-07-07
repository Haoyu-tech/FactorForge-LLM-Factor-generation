# issuance_level_change_mom_eqnetis_at_24

```mermaid
flowchart TD
  H["Economic hypothesis: Both persistent financing and rising financing are negative; momentum and short-term reversal control delayed price adjustment."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$ret_12_1"] --> T
  F3["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["TS_MEAN"] --> T
  O3["DELTA"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: -RANK(TS_MEAN($eqnetis_at, 24)) - RANK(DELTA($eqnetis_at, 24)) + RANK($ret_12_1) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0310, IC_t=+6.55, LS_SR=+0.65"]
```

- **Family:** `issuance_momentum_ts`
- **Structure:** time-series transform
- **Fields:** `$eqnetis_at, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, TS_MEAN, DELTA, ADD, SUBTRACT`
- **Expression:** `-RANK(TS_MEAN($eqnetis_at, 24)) - RANK(DELTA($eqnetis_at, 24)) + RANK($ret_12_1) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0310, IC_t=+6.55, LS_SR=+0.65
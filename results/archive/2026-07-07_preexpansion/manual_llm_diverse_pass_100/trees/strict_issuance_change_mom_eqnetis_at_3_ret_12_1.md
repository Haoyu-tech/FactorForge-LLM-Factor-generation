# strict_issuance_change_mom_eqnetis_at_3_ret_12_1

```mermaid
flowchart TD
  H["Economic hypothesis: Low persistent issuance and falling issuance identify disciplined firms; momentum and short-term reversal capture delayed price adjustment."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$ret_12_1"] --> T
  F3["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["TS_MEAN"] --> T
  O3["DELTA"] --> T
  O4["ADD"] --> T
  O5["SUBTRACT"] --> T
  T --> E["Expression: -RANK(TS_MEAN($eqnetis_at, 3)) - RANK(DELTA($eqnetis_at, 3)) + RANK($ret_12_1) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0321, IC_t=+7.00, LS_SR=+0.67"]
```

- **Family:** `strict_issuance_momentum`
- **Structure:** time-series transform
- **Fields:** `$eqnetis_at, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, TS_MEAN, DELTA, ADD, SUBTRACT`
- **Expression:** `-RANK(TS_MEAN($eqnetis_at, 3)) - RANK(DELTA($eqnetis_at, 3)) + RANK($ret_12_1) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0321, IC_t=+7.00, LS_SR=+0.67
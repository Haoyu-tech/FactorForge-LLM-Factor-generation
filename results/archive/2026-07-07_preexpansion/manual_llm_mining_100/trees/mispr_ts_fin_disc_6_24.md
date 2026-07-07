# mispr_ts_fin_disc_6_24

```mermaid
flowchart TD
  H["Economic hypothesis: Persistent mispricing should earn stronger reversals when equity issuance and asset growth are restrained."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$eqnetis_at"] --> T
  F3["$mispricing_mgmt"] --> T
  F4["$mispricing_perf"] --> T
  O1["RANK"] --> T
  O2["TS_MEAN"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(TS_MEAN($mispricing_perf, 6) + TS_MEAN($mispricing_mgmt, 6)) - RANK(TS_MEAN($eqnetis_at, 24)) - RANK($at_gr1)"]
  E --> M["Metrics: IC=+0.0269, IC_t=+7.32, LS_SR=+0.80"]
```

- **Family:** `mispricing_financing_ts`
- **Structure:** time-series transform
- **Fields:** `$at_gr1, $eqnetis_at, $mispricing_mgmt, $mispricing_perf`
- **Operators:** `RANK, TS_MEAN, ADD, SUBTRACT`
- **Expression:** `RANK(TS_MEAN($mispricing_perf, 6) + TS_MEAN($mispricing_mgmt, 6)) - RANK(TS_MEAN($eqnetis_at, 24)) - RANK($at_gr1)`
- **Metrics:** IC=+0.0269, IC_t=+7.32, LS_SR=+0.80
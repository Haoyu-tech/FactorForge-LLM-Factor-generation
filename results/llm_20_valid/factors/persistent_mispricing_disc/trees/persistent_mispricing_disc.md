# persistent_mispricing_disc

```mermaid
flowchart TD
  H["Economic hypothesis: Persistent (not transient) mispricing plus persistently low issuance identifies durable anomaly exposure."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$mispricing_mgmt"] --> T
  F3["$mispricing_perf"] --> T
  O1["RANK"] --> T
  O2["TS_MEAN"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(TS_MEAN($mispricing_perf, 6) + TS_MEAN($mispricing_mgmt, 6)) - RANK(TS_MEAN($eqnetis_at, 12))"]
  E --> M["Metrics: IC=+0.0287, IC_t=+7.08, LS_SR=+0.71"]
```

- **Family:** ``
- **Structure:** time-series transform
- **Fields:** `$eqnetis_at, $mispricing_mgmt, $mispricing_perf`
- **Operators:** `RANK, TS_MEAN, ADD, SUBTRACT`
- **Expression:** `RANK(TS_MEAN($mispricing_perf, 6) + TS_MEAN($mispricing_mgmt, 6)) - RANK(TS_MEAN($eqnetis_at, 12))`
- **Metrics:** IC=+0.0287, IC_t=+7.08, LS_SR=+0.71
# mispr_ts_fin_qual_12_6

```mermaid
flowchart TD
  H["Economic hypothesis: Persistent mispricing is more credible when supported by profitability and capital discipline."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$at_gr1"] --> T
  F2["$eqnetis_at"] --> T
  F3["$gp_at"] --> T
  F4["$mispricing_mgmt"] --> T
  F5["$mispricing_perf"] --> T
  O1["RANK"] --> T
  O2["TS_MEAN"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(TS_MEAN($mispricing_perf, 12) + TS_MEAN($mispricing_mgmt, 12)) - RANK(TS_MEAN($eqnetis_at, 6)) - RANK($at_gr1) + RANK($gp_at)"]
  E --> M["Metrics: IC=+0.0239, IC_t=+6.07, LS_SR=+0.72"]
```

- **Family:** `mispricing_financing_ts`
- **Structure:** time-series transform
- **Fields:** `$at_gr1, $eqnetis_at, $gp_at, $mispricing_mgmt, $mispricing_perf`
- **Operators:** `RANK, TS_MEAN, ADD, SUBTRACT`
- **Expression:** `RANK(TS_MEAN($mispricing_perf, 12) + TS_MEAN($mispricing_mgmt, 12)) - RANK(TS_MEAN($eqnetis_at, 6)) - RANK($at_gr1) + RANK($gp_at)`
- **Metrics:** IC=+0.0239, IC_t=+6.07, LS_SR=+0.72
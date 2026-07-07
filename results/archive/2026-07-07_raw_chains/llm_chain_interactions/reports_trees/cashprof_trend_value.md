# cashprof_trend_value

```mermaid
flowchart TD
  H["Economic hypothesis: Time-series: improving cash-profitability trend plus cheap valuation and low issuance captures underreacted quality recovery."] --> S["Structure: time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$cop_at"] --> T
  F3["$eqnetis_at"] --> T
  O1["RANK"] --> T
  O2["TS_ZSCORE"] --> T
  O3["ADD"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(TS_ZSCORE($cop_at, 12)) + RANK($be_me) - RANK($eqnetis_at)"]
  E --> M["Metrics: IC=+0.0211, IC_t=+4.99, LS_SR=+0.68"]
```

- **Family:** `llm`
- **Structure:** time-series transform
- **Fields:** `$be_me, $cop_at, $eqnetis_at`
- **Operators:** `RANK, TS_ZSCORE, ADD, SUBTRACT`
- **Expression:** `RANK(TS_ZSCORE($cop_at, 12)) + RANK($be_me) - RANK($eqnetis_at)`
- **Metrics:** IC=+0.0211, IC_t=+4.99, LS_SR=+0.68
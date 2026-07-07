# profit_accel_x_value

```mermaid
flowchart TD
  H["Economic hypothesis: Time-series x multiplicative: a profitability improvement is worth more when the firm is cheap; tilt toward safe firms."] --> S["Structure: multiplicative interaction, time-series transform"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$cop_at"] --> T
  F3["$qmj_safety"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["TS_ZSCORE"] --> T
  O4["MULTIPLY"] --> T
  O5["ADD"] --> T
  T --> E["Expression: RANK(TS_ZSCORE($cop_at, 12) * ZSCORE($be_me)) + RANK($qmj_safety)"]
  E --> M["Metrics: IC=+0.0060, IC_t=+1.68, LS_SR=-0.18"]
```

- **Family:** `llm`
- **Structure:** multiplicative interaction, time-series transform
- **Fields:** `$be_me, $cop_at, $qmj_safety`
- **Operators:** `RANK, ZSCORE, TS_ZSCORE, MULTIPLY, ADD`
- **Expression:** `RANK(TS_ZSCORE($cop_at, 12) * ZSCORE($be_me)) + RANK($qmj_safety)`
- **Metrics:** IC=+0.0060, IC_t=+1.68, LS_SR=-0.18
# mispr_profit_lowrisk

```mermaid
flowchart TD
  H["Economic hypothesis: Mispricing supported by profitability and concentrated in low-idio-vol, more investable names."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$gp_at"] --> T
  F2["$ivol_ff3_21d"] --> T
  F3["$mispricing_mgmt"] --> T
  F4["$mispricing_perf"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($mispricing_perf) + RANK($mispricing_mgmt) + RANK($gp_at) - RANK($ivol_ff3_21d)"]
  E --> M["Metrics: IC=+0.0274, IC_t=+5.29, LS_SR=+0.32"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$gp_at, $ivol_ff3_21d, $mispricing_mgmt, $mispricing_perf`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) + RANK($gp_at) - RANK($ivol_ff3_21d)`
- **Metrics:** IC=+0.0274, IC_t=+5.29, LS_SR=+0.32
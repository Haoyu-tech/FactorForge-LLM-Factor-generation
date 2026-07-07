# low_duration_quality

```mermaid
flowchart TD
  H["Economic hypothesis: Dechow et al. (2004) / Weber (2018): low equity duration (near-term cash flows) earns a value-like premium; Asness-Frazzini-Pedersen quality; lower market beta. Safe, cash-now, high-quality firms."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$beta_60m"] --> T
  F2["$eq_dur"] --> T
  F3["$qmj"] --> T
  O1["RANK"] --> T
  O2["SUBTRACT"] --> T
  T --> E["Expression: RANK($qmj) - RANK($eq_dur) - RANK($beta_60m)"]
  E --> M["Metrics: IC=+0.0253, IC_t=+3.69, LS_SR=+0.23"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$beta_60m, $eq_dur, $qmj`
- **Operators:** `RANK, SUBTRACT`
- **Expression:** `RANK($qmj) - RANK($eq_dur) - RANK($beta_60m)`
- **Metrics:** IC=+0.0253, IC_t=+3.69, LS_SR=+0.23
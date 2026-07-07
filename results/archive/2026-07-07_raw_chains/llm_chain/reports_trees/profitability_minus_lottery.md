# profitability_minus_lottery

```mermaid
flowchart TD
  H["Economic hypothesis: Bali et al. (2011) MAX/lottery effect and Ang et al. (2006) idiosyncratic-volatility anomaly: high-MAX, high-idio-vol stocks underperform. Long cash-profitable, non-lottery, low-idio-vol names."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$cop_at"] --> T
  F2["$ivol_capm_21d"] --> T
  F3["$rmax5_21d"] --> T
  O1["RANK"] --> T
  O2["SUBTRACT"] --> T
  T --> E["Expression: RANK($cop_at) - RANK($rmax5_21d) - RANK($ivol_capm_21d)"]
  E --> M["Metrics: IC=+0.0267, IC_t=+4.23, LS_SR=+0.20"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$cop_at, $ivol_capm_21d, $rmax5_21d`
- **Operators:** `RANK, SUBTRACT`
- **Expression:** `RANK($cop_at) - RANK($rmax5_21d) - RANK($ivol_capm_21d)`
- **Metrics:** IC=+0.0267, IC_t=+4.23, LS_SR=+0.20
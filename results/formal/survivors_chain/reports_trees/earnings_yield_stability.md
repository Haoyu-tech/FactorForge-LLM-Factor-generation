# earnings_yield_stability

```mermaid
flowchart TD
  H["Economic hypothesis: Ratio: earnings yield scaled by earnings volatility rewards stable high-yield earners (quality of earnings-to-price), plus cash profitability."] --> S["Structure: ratio / risk scaling"]
  S --> T["Transform / combine signals"]
  F1["$cop_at"] --> T
  F2["$ni_ivol"] --> T
  F3["$ni_me"] --> T
  O1["RANK"] --> T
  O2["DIVIDE"] --> T
  O3["ADD"] --> T
  T --> E["Expression: RANK($ni_me / ($ni_ivol + 1)) + RANK($cop_at)"]
  E --> M["Metrics: IC=+0.0290, IC_t=+7.03, LS_SR=+0.73"]
```

- **Family:** `llm`
- **Structure:** ratio / risk scaling
- **Fields:** `$cop_at, $ni_ivol, $ni_me`
- **Operators:** `RANK, DIVIDE, ADD`
- **Expression:** `RANK($ni_me / ($ni_ivol + 1)) + RANK($cop_at)`
- **Metrics:** IC=+0.0290, IC_t=+7.03, LS_SR=+0.73
# pead_earnings_revenue_surprise

```mermaid
flowchart TD
  H["Economic hypothesis: Post-earnings-announcement drift: standardized unexpected earnings and revenue surprises predict continued drift; revenue surprise confirms the earnings signal is real. Guard against one-month reversal."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$niq_su"] --> T
  F2["$ret_1_0"] --> T
  F3["$saleq_su"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($niq_su) + RANK($saleq_su) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0146, IC_t=+3.59, LS_SR=+0.38"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$niq_su, $ret_1_0, $saleq_su`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($niq_su) + RANK($saleq_su) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0146, IC_t=+3.59, LS_SR=+0.38
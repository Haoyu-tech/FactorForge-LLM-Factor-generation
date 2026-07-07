# surprise_x_illiquidity

```mermaid
flowchart TD
  H["Economic hypothesis: Multiplicative: post-earnings-announcement drift is stronger among illiquid, limits-to-arbitrage stocks (Amihud); earnings surprise interacted with illiquidity, guarded against reversal."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$ami_126d"] --> T
  F2["$niq_su"] --> T
  F3["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($niq_su) * ZSCORE($ami_126d)) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0105, IC_t=+2.25, LS_SR=+0.25"]
```

- **Family:** `llm`
- **Structure:** multiplicative interaction
- **Fields:** `$ami_126d, $niq_su, $ret_1_0`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($niq_su) * ZSCORE($ami_126d)) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0105, IC_t=+2.25, LS_SR=+0.25
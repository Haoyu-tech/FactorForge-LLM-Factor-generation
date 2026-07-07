# earnings_streak_momentum

```mermaid
flowchart TD
  H["Economic hypothesis: Earnings-increase streaks (Loh-Warachka earnings momentum) plus price momentum, guarded against short-term reversal: fundamental and price underreaction reinforce each other."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$ni_inc8q"] --> T
  F2["$ret_12_1"] --> T
  F3["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($ni_inc8q) + RANK($ret_12_1) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0259, IC_t=+4.90, LS_SR=+0.37"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$ni_inc8q, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($ni_inc8q) + RANK($ret_12_1) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0259, IC_t=+4.90, LS_SR=+0.37
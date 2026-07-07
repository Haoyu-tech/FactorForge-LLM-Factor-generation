# value_x_quality

```mermaid
flowchart TD
  H["Economic hypothesis: Multiplicative: value and quality reinforce each other (cheap AND profitable, Novy-Marx / Asness), penalizing balance-sheet bloat (net operating assets)."] --> S["Structure: multiplicative interaction"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$noa_at"] --> T
  F3["$qmj_prof"] --> T
  O1["RANK"] --> T
  O2["ZSCORE"] --> T
  O3["MULTIPLY"] --> T
  O4["SUBTRACT"] --> T
  T --> E["Expression: RANK(ZSCORE($be_me) * ZSCORE($qmj_prof)) - RANK($noa_at)"]
  E --> M["Metrics: IC=+0.0075, IC_t=+2.27, LS_SR=+0.53"]
```

- **Family:** `llm`
- **Structure:** multiplicative interaction
- **Fields:** `$be_me, $noa_at, $qmj_prof`
- **Operators:** `RANK, ZSCORE, MULTIPLY, SUBTRACT`
- **Expression:** `RANK(ZSCORE($be_me) * ZSCORE($qmj_prof)) - RANK($noa_at)`
- **Metrics:** IC=+0.0075, IC_t=+2.27, LS_SR=+0.53
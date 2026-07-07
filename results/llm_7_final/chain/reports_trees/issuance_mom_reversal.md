# issuance_mom_reversal

```mermaid
flowchart TD
  H["Economic hypothesis: Low equity and debt financing plus intermediate momentum, guarded against short-term reversal = capital discipline + underreaction."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$dbnetis_at"] --> T
  F2["$eqnetis_at"] --> T
  F3["$ret_12_1"] --> T
  F4["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: -RANK($eqnetis_at) - RANK($dbnetis_at) + RANK($ret_12_1) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0340, IC_t=+7.37, LS_SR=+0.76"]
```

- **Family:** `llm`
- **Structure:** rank-sum composite
- **Fields:** `$dbnetis_at, $eqnetis_at, $ret_12_1, $ret_1_0`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `-RANK($eqnetis_at) - RANK($dbnetis_at) + RANK($ret_12_1) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0340, IC_t=+7.37, LS_SR=+0.76
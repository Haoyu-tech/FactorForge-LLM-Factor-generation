# strict_value_quality_issue_be_me_gp_at_eqnetis_at

```mermaid
flowchart TD
  H["Economic hypothesis: Cheap profitable firms with low issuance and short-term reversal control combine value, quality, and financing discipline."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$be_me"] --> T
  F2["$eqnetis_at"] --> T
  F3["$gp_at"] --> T
  F4["$ret_1_0"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($be_me) + RANK($gp_at) - RANK($eqnetis_at) - RANK($ret_1_0)"]
  E --> M["Metrics: IC=+0.0315, IC_t=+6.16, LS_SR=+0.77"]
```

- **Family:** `strict_value_quality_issuance`
- **Structure:** rank-sum composite
- **Fields:** `$be_me, $eqnetis_at, $gp_at, $ret_1_0`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($be_me) + RANK($gp_at) - RANK($eqnetis_at) - RANK($ret_1_0)`
- **Metrics:** IC=+0.0315, IC_t=+6.16, LS_SR=+0.77
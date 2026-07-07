# mispr_mgmt_accrual

```mermaid
flowchart TD
  H["Economic hypothesis: The management mispricing cluster (net issuance, accruals, investment) reinforced by low accruals, low issuance, profitability."] --> S["Structure: rank-sum composite"]
  S --> T["Transform / combine signals"]
  F1["$eqnetis_at"] --> T
  F2["$gp_at"] --> T
  F3["$mispricing_mgmt"] --> T
  F4["$oaccruals_at"] --> T
  O1["RANK"] --> T
  O2["ADD"] --> T
  O3["SUBTRACT"] --> T
  T --> E["Expression: RANK($mispricing_mgmt) - RANK($oaccruals_at) - RANK($eqnetis_at) + RANK($gp_at)"]
  E --> M["Metrics: IC=+0.0252, IC_t=+7.18, LS_SR=+1.07"]
```

- **Family:** ``
- **Structure:** rank-sum composite
- **Fields:** `$eqnetis_at, $gp_at, $mispricing_mgmt, $oaccruals_at`
- **Operators:** `RANK, ADD, SUBTRACT`
- **Expression:** `RANK($mispricing_mgmt) - RANK($oaccruals_at) - RANK($eqnetis_at) + RANK($gp_at)`
- **Metrics:** IC=+0.0252, IC_t=+7.18, LS_SR=+1.07
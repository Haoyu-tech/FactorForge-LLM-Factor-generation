# LLM Formula Tree: mispr_mgmt_accrual

```mermaid
flowchart TD
  N0["ADD"]
  N1["SUBTRACT"]
  N0 --> N1
  N2["SUBTRACT"]
  N1 --> N2
  N3["RANK"]
  N2 --> N3
  N4["＄mispricing_mgmt"]
  N3 --> N4
  N5["RANK"]
  N2 --> N5
  N6["＄oaccruals_at"]
  N5 --> N6
  N7["RANK"]
  N1 --> N7
  N8["＄eqnetis_at"]
  N7 --> N8
  N9["RANK"]
  N0 --> N9
  N10["＄gp_at"]
  N9 --> N10
```

- **Expression:** `RANK($mispricing_mgmt) - RANK($oaccruals_at) - RANK($eqnetis_at) + RANK($gp_at)`
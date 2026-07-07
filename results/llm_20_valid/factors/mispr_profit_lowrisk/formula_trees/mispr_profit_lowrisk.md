# LLM Formula Tree: mispr_profit_lowrisk

```mermaid
flowchart TD
  N0["SUBTRACT"]
  N1["ADD"]
  N0 --> N1
  N2["ADD"]
  N1 --> N2
  N3["RANK"]
  N2 --> N3
  N4["＄mispricing_perf"]
  N3 --> N4
  N5["RANK"]
  N2 --> N5
  N6["＄mispricing_mgmt"]
  N5 --> N6
  N7["RANK"]
  N1 --> N7
  N8["＄gp_at"]
  N7 --> N8
  N9["RANK"]
  N0 --> N9
  N10["＄ivol_ff3_21d"]
  N9 --> N10
```

- **Expression:** `RANK($mispricing_perf) + RANK($mispricing_mgmt) + RANK($gp_at) - RANK($ivol_ff3_21d)`
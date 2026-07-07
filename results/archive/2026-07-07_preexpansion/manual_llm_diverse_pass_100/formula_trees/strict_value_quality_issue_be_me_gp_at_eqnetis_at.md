# LLM Formula Tree: strict_value_quality_issue_be_me_gp_at_eqnetis_at

```mermaid
flowchart TD
  N0["SUBTRACT"]
  N1["SUBTRACT"]
  N0 --> N1
  N2["ADD"]
  N1 --> N2
  N3["RANK"]
  N2 --> N3
  N4["＄be_me"]
  N3 --> N4
  N5["RANK"]
  N2 --> N5
  N6["＄gp_at"]
  N5 --> N6
  N7["RANK"]
  N1 --> N7
  N8["＄eqnetis_at"]
  N7 --> N8
  N9["RANK"]
  N0 --> N9
  N10["＄ret_1_0"]
  N9 --> N10
```

- **Expression:** `RANK($be_me) + RANK($gp_at) - RANK($eqnetis_at) - RANK($ret_1_0)`
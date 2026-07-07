# LLM Formula Tree: risk_scaled_value_quality_24

```mermaid
flowchart TD
  N0["SUBTRACT"]
  N1["RANK"]
  N0 --> N1
  N2["DIVIDE"]
  N1 --> N2
  N3["ADD"]
  N2 --> N3
  N4["＄be_me"]
  N3 --> N4
  N5["＄gp_at"]
  N3 --> N5
  N6["TS_STD"]
  N2 --> N6
  N7["＄return"]
  N6 --> N7
  N8["window=24"]
  N6 --> N8
  N9["RANK"]
  N0 --> N9
  N10["＄ivol_ff3_21d"]
  N9 --> N10
```

- **Expression:** `RANK(($be_me + $gp_at) / TS_STD($return, 24)) - RANK($ivol_ff3_21d)`
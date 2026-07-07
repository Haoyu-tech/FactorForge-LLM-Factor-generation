# LLM Formula Tree: profit_accel_x_value

```mermaid
flowchart TD
  N0["ADD"]
  N1["RANK"]
  N0 --> N1
  N2["MULTIPLY"]
  N1 --> N2
  N3["TS_ZSCORE"]
  N2 --> N3
  N4["＄cop_at"]
  N3 --> N4
  N5["window=12"]
  N3 --> N5
  N6["ZSCORE"]
  N2 --> N6
  N7["＄be_me"]
  N6 --> N7
  N8["RANK"]
  N0 --> N8
  N9["＄qmj_safety"]
  N8 --> N9
```

- **Expression:** `RANK(TS_ZSCORE($cop_at, 12) * ZSCORE($be_me)) + RANK($qmj_safety)`
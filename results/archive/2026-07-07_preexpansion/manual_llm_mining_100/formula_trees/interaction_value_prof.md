# LLM Formula Tree: interaction_value_prof

```mermaid
flowchart TD
  N0["SUBTRACT"]
  N1["RANK"]
  N0 --> N1
  N2["MULTIPLY"]
  N1 --> N2
  N3["ZSCORE"]
  N2 --> N3
  N4["＄be_me"]
  N3 --> N4
  N5["ZSCORE"]
  N2 --> N5
  N6["＄op_at"]
  N5 --> N6
  N7["RANK"]
  N0 --> N7
  N8["＄eqnetis_at"]
  N7 --> N8
```

- **Expression:** `RANK(ZSCORE($be_me) * ZSCORE($op_at)) - RANK($eqnetis_at)`
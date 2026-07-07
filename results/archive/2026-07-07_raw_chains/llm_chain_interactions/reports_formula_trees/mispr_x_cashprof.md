# LLM Formula Tree: mispr_x_cashprof

```mermaid
flowchart TD
  N0["SUBTRACT"]
  N1["RANK"]
  N0 --> N1
  N2["MULTIPLY"]
  N1 --> N2
  N3["ZSCORE"]
  N2 --> N3
  N4["＄mispricing_mgmt"]
  N3 --> N4
  N5["ZSCORE"]
  N2 --> N5
  N6["＄cop_at"]
  N5 --> N6
  N7["RANK"]
  N0 --> N7
  N8["＄eqnetis_at"]
  N7 --> N8
```

- **Expression:** `RANK(ZSCORE($mispricing_mgmt) * ZSCORE($cop_at)) - RANK($eqnetis_at)`
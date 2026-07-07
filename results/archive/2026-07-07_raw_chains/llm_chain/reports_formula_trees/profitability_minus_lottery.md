# LLM Formula Tree: profitability_minus_lottery

```mermaid
flowchart TD
  N0["SUBTRACT"]
  N1["SUBTRACT"]
  N0 --> N1
  N2["RANK"]
  N1 --> N2
  N3["＄cop_at"]
  N2 --> N3
  N4["RANK"]
  N1 --> N4
  N5["＄rmax5_21d"]
  N4 --> N5
  N6["RANK"]
  N0 --> N6
  N7["＄ivol_capm_21d"]
  N6 --> N7
```

- **Expression:** `RANK($cop_at) - RANK($rmax5_21d) - RANK($ivol_capm_21d)`
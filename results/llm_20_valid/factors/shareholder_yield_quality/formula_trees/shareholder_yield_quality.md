# LLM Formula Tree: shareholder_yield_quality

```mermaid
flowchart TD
  N0["SUBTRACT"]
  N1["ADD"]
  N0 --> N1
  N2["RANK"]
  N1 --> N2
  N3["＄eqnpo_me"]
  N2 --> N3
  N4["RANK"]
  N1 --> N4
  N5["＄cop_at"]
  N4 --> N5
  N6["RANK"]
  N0 --> N6
  N7["＄eqnetis_at"]
  N6 --> N7
```

- **Expression:** `RANK($eqnpo_me) + RANK($cop_at) - RANK($eqnetis_at)`
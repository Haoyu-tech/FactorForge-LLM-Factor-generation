# LLM Formula Tree: issuance_level_change_mom_chcsho_12m_12

```mermaid
flowchart TD
  N0["NEGATE"]
  N1["SUBTRACT"]
  N0 --> N1
  N2["ADD"]
  N1 --> N2
  N3["SUBTRACT"]
  N2 --> N3
  N4["RANK"]
  N3 --> N4
  N5["TS_MEAN"]
  N4 --> N5
  N6["＄chcsho_12m"]
  N5 --> N6
  N7["window=12"]
  N5 --> N7
  N8["RANK"]
  N3 --> N8
  N9["DELTA"]
  N8 --> N9
  N10["＄chcsho_12m"]
  N9 --> N10
  N11["window=12"]
  N9 --> N11
  N12["RANK"]
  N2 --> N12
  N13["＄ret_12_1"]
  N12 --> N13
  N14["RANK"]
  N1 --> N14
  N15["＄ret_1_0"]
  N14 --> N15
```

- **Expression:** `-RANK(TS_MEAN($chcsho_12m, 12)) - RANK(DELTA($chcsho_12m, 12)) + RANK($ret_12_1) - RANK($ret_1_0)`
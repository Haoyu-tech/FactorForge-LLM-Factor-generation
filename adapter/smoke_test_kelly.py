# -*- coding: utf-8 -*-
"""
Multi-category smoke test on the full-universe + Kelly-153 panel.
One representative factor per data type, plus cross-category combos.
"""
from evaluate_ic import summary, print_table

TESTS = {
    "value":        "$be_me",
    "quality":      "$gp_at",
    "momentum":     "$ret_12_1",
    "low_risk":     "-1 * $ivol_ff3_21d",
    "illiquidity":  "$ami_126d",
    "issuance":     "-1 * $eqnetis_at",
    "mispricing":   "$mispricing_perf",
    "safety":       "$qmj_safety",
    "investment":   "-1 * $at_gr1",
    "combo_QtMnV":  "RANK($gp_at) + RANK($be_me) - RANK($ivol_ff3_21d) - RANK($eqnetis_at)",
    "combo_ts":     "RANK($ret_12_1) - RANK(TS_STD($return, 12))",
}
START = "1972-01-01"

if __name__ == "__main__":
    rows = []
    for name, expr in TESTS.items():
        r = summary(expr, start=START)
        r["expr"] = f"{name:12} {expr}"
        rows.append(r)
    print(f"\nS&P 500 full universe + Kelly-153 - multi-category factor IC ({START}+)\n")
    print_table(rows)


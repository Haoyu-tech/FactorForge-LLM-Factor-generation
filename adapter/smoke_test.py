# -*- coding: utf-8 -*-
"""
End-to-end smoke test of the QuantaAlpha->WRDS monthly adapter.
Computes a set of well-known factors on the S&P 500 monthly panel and reports
IC/ICIR vs next-month excess return. Signs should match the literature:
  momentum +, short-term reversal +, value(be_me) +, profitability(gp_at) +,
  low-vol(-ivol) +.  This validates parser + function_lib + panel + evaluator.
"""
from evaluate_ic import summary, print_table

TESTS = {
    "momentum_12_1":        "$ret_12_1",
    "short_rev":            "-1 * $return",
    "value_bm":             "$be_me",
    "profitability":        "$gp_at",
    "low_vol":              "-1 * $ivol_ff3_21d",
    "size_small":           "-1 * $me",
    "ts_mom_zscore":        "TS_ZSCORE($ret_12_1, 12)",
    "quality_minus_value":  "RANK($gp_at) - RANK($be_me)",
    "qual_value_combo":     "RANK($gp_at) + RANK($be_me) - RANK($ivol_ff3_21d)",
}

START = "1985-01-01"   # characteristics well-populated from mid-80s

if __name__ == "__main__":
    rows = []
    for name, expr in TESTS.items():
        r = summary(expr, start=START)
        r["expr"] = f"{name:22} {expr}"
        rows.append(r)
    print(f"\nS&P 500 monthly factor IC  ({START}+ , next-month excess return)\n")
    print_table(rows)


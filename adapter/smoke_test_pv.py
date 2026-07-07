# -*- coding: utf-8 -*-
"""
Smoke test on the FULL official-universe price/volume panel (~500/month).
Only price/volume fields exist here ($open/$high/$low/$close/$volume/$me/$return),
so factors are built from those. Expected signs: momentum +, short-rev +,
low-vol +.  Validates parser + function_lib + full panel + evaluator.
"""
from evaluate_ic import summary, print_table

TESTS = {
    "mom_12_1":     "DELAY($close, 1) / DELAY($close, 12) - 1",   # 12-1 momentum
    "mom_12_0":     "$close / DELAY($close, 12) - 1",             # 12m momentum
    "short_rev":    "-1 * $return",                              # 1m reversal
    "vol_12m":      "-1 * TS_STD($return, 12)",                   # low-volatility
    "size":         "-1 * $me",                                  # size (large-cap)
    "turnover":     "-1 * ($volume / DELAY($volume, 1))",         # volume change
    "mom_x_lowvol": "RANK(DELAY($close,1)/DELAY($close,12)-1) - RANK(TS_STD($return,12))",
}

START = "1965-01-01"   # modern 500-stock index era

if __name__ == "__main__":
    rows = []
    for name, expr in TESTS.items():
        r = summary(expr, start=START)
        r["expr"] = f"{name:14} {expr}"
        rows.append(r)
    print(f"\nS&P 500 FULL universe - price/volume factor IC ({START}+)\n")
    print_table(rows)


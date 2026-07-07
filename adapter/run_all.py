# -*- coding: utf-8 -*-
"""
One-shot orchestrator: run the whole evaluation suite into ONE clean folder
(results/final/) and render a single summary figure. Mechanical baseline = GP only.

Layout produced:
  results/final/
    1_factor_lab/        per-factor reports + academic_table_{vw,ew}.tex + summary.csv
    2_spanning/          spanning_table.{md,tex,csv}
    3_walk_forward/      walk_forward.{md,csv}
    4_multiple_testing/  multiple_testing.{md,csv}
    5_horse_race_full/   full-grammar GP search vs LLM (+ gate/ = GP winner through strict gate)
    6_fama_macbeth/      firm-level Fama-MacBeth (factor slope after controls)
    7_llm_mining_100/    LLM-mined candidates + economic/formula trees + strict gate reports
    SUMMARY.png          headline figure
    README.md            what each folder is + headline numbers

Run:  python adapter/run_all.py --full-trials 10
"""
import argparse
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
sys.path.insert(0, str(Path(__file__).resolve().parent))
import factor_lab
import spanning
import walk_forward
import gp_search_full
import multiple_testing
import fama_macbeth
import manual_llm_mine
from factor_lab import ROOT
from llm_factor.config import path, sample, search
from llm_factor.manifest import default_input_paths, write_manifest

FINAL = path("results_root") / "final"
FACTORS = factor_lab.DEFAULT_FACTORS                       # name -> (expr, rationale)
EXPRS = {k: v[0] for k, v in FACTORS.items()}             # name -> expr


def make_summary(final, fl_sdf):
    gate = pd.read_csv(final / "5_horse_race_full" / "gate" / "summary.csv")
    llm = fl_sdf.assign(group="LLM (economic)")
    win = gate.assign(group="mechanical search")
    cols = ["name", "VW_FF5UMDa_t", "VW_FF5UMDa_t_test", "group"]
    allf = pd.concat([llm[cols], win[cols]], ignore_index=True)

    fig, ax = plt.subplots(1, 2, figsize=(15, 6))
    # Panel 1: OOS VW FF5+UMD alpha t, LLM vs GP search.
    d = allf.sort_values("VW_FF5UMDa_t_test")
    colors = ["#1a9850" if abs(t) > 1.96 else "#bdbdbd" for t in d["VW_FF5UMDa_t_test"]]
    labels = [f"{n}\n[{g}]" for n, g in zip(d["name"], d["group"])]
    ax[0].barh(range(len(d)), d["VW_FF5UMDa_t_test"], color=colors)
    ax[0].set_yticks(range(len(d))); ax[0].set_yticklabels(labels, fontsize=8)
    ax[0].axvline(1.96, color="#d73027", ls="--", lw=1, label="|t|=1.96")
    ax[0].axvline(-1.96, color="#d73027", ls="--", lw=1)
    ax[0].set_xlabel("OOS value-weighted FF5+UMD alpha  (Newey-West t)")
    ax[0].set_title("Out-of-sample survival under the strict gate\n(green = significant)")
    ax[0].legend(fontsize=8, loc="lower right")

    # ---- panel 2: EW vs VW full-sample alpha t for LLM factors (value-weight shrinkage) ----
    fl = fl_sdf.set_index("name")
    names = list(fl.index)
    x = np.arange(len(names)); w = 0.38
    ax[1].bar(x - w/2, fl["EW_FF5UMDa_t"], w, label="equal-weighted", color="#4575b4")
    ax[1].bar(x + w/2, fl["VW_FF5UMDa_t"], w, label="value-weighted", color="#fc8d59")
    ax[1].axhline(1.96, color="#d73027", ls="--", lw=1)
    ax[1].set_xticks(x); ax[1].set_xticklabels(names, rotation=30, ha="right", fontsize=8)
    ax[1].set_ylabel("Full-sample FF5+UMD alpha  (Newey-West t)")
    ax[1].set_title("Value-weighting shrinks the alpha (large-cap reality)")
    ax[1].legend(fontsize=8)

    fig.suptitle("LLM economic factors survive rigorous asset-pricing scrutiny; "
                 "mechanical-search winners do not", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(final / "SUMMARY.png", dpi=130)
    plt.close(fig)


def write_readme(final, fl_sdf):
    gate = pd.read_csv(final / "5_horse_race_full" / "gate" / "summary.csv")

    def pct(x):
        return f"{x*100:+.1f}%" if pd.notna(x) else "--"

    L = ["# LLM-Factor - consolidated results", "",
         "One pass. Mechanical-search baseline = full-grammar GP only; random search is excluded.", "",
         "![summary](SUMMARY.png)", "",
         "## Reading the results: full sample vs OOS", "",
         "- **Full sample** = 1972-01 .. 2025 (all months). Maximum statistical power; this is the "
         "**headline result**, as in standard empirical asset-pricing papers.",
         "- **OOS (out-of-sample)** = post-2000-12-31 only - held out, not used to pick the factors. "
         "Fewer months -> lower t, but the honest test of persistence / anti data-snooping. "
         "(Note: full sample includes OOS.)",
         "- Because a full-sample headline has no OOS protection, the significance hurdle follows "
         "**Harvey-Liu-Zhu (2016): |t| > 3.0** (not 1.96), to suppress data-snooping.",
         "- **OOS + walk-forward (`3_walk_forward/`) are reported as robustness**: a full-sample-strong "
         "factor that decays OOS (e.g. `qual_val_mom`) is flagged, not credited.",
         "- The PASS verdict in `1_factor_lab/` is stricter still: VW FF5+UMD significant in "
         "**both full AND OOS**.", "",
         "## Headline - full sample, value-weighted, FF5+UMD alpha", "",
         "| Factor | alpha (ann) | t (NW) | HLZ t>3 | monotone | OOS t | verdict |",
         "|---|---|---|---|---|---|---|"]
    fl = fl_sdf.sort_values("VW_FF5UMDa_t", key=lambda s: s.abs(), ascending=False)
    for _, r in fl.iterrows():
        hlz = "PASS" if abs(r["VW_FF5UMDa_t"]) > 3 else "FAIL"
        L.append(f"| {r['name']} | {pct(r['VW_FF5UMDa_ann'])} | {r['VW_FF5UMDa_t']:+.2f} | {hlz} | "
                 f"{r['mono']:+.2f} | {r['VW_FF5UMDa_t_test']:+.2f} | {r['verdict']} |")

    L += ["", "## Robustness - OOS value-weighted FF5+UMD alpha t", "",
          "| Factor | group | OOS alpha t | verdict |", "|---|---|---|---|"]
    for _, r in fl_sdf.iterrows():
        L.append(f"| {r['name']} | LLM | {r['VW_FF5UMDa_t_test']:+.2f} | {r['verdict']} |")
    for _, r in gate.iterrows():
        L.append(f"| {r['name']} | GP search | {r['VW_FF5UMDa_t_test']:+.2f} | {r['verdict']} |")

    L += ["", "## Folders", "",
          "- `1_factor_lab/` - per-factor reports, `academic_table_vw.tex` (main) / `_ew.tex`, summary.csv",
          "- `2_spanning/` - increment over components and the Kelly anomaly zoo",
          "- `3_walk_forward/` - expanding-window 3-yr OOS blocks (stability)",
          "- `4_multiple_testing/` - HLZ t>3, Bonferroni, Deflated Sharpe",
          "- `5_horse_race_full/` - full-grammar GP search vs LLM; `gate/` = GP winner through the strict gate",
          "- `6_fama_macbeth/` - firm-level Fama-MacBeth: factor slope after size/B-M/momentum/beta controls",
          "- `7_llm_mining_100/` - 100 LLM-style mined candidates, economic trees, GP-style formula trees, and strict gate plots"]
    (final / "README.md").write_text("\n".join(L), encoding="utf-8")


def _archive_existing_final():
    if FINAL.exists():
        archive = path("results_root") / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        dst = archive / f"final_{pd.Timestamp.now():%Y%m%d_%H%M%S}"
        shutil.move(str(FINAL), str(dst))
        print(f"archived previous final -> {dst}")


def _copy_tree(src: Path, dst: Path):
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def run_llm_mining_bundle(final: Path, target=100, gate_count=100, min_ic_t=2.0):
    """Refresh manual LLM mining artifacts and collect them into final results.

    The mining ledger is IC-screened. The gate folder below is the stricter
    asset-pricing report that creates the same kind of 4-panel PNG as
    financing_reversal_guard.png.
    """
    print("\n########## 7. LLM mining artifacts + strict gate ##########")
    manual_llm_mine.main(target=target, batch_size=120, min_ic_t=min_ic_t)

    src = manual_llm_mine.OUTDIR
    dst = final / "7_llm_mining_100"
    dst.mkdir(parents=True, exist_ok=True)
    for fn in ["progress.json", "valid_factors.csv", "manual_llm_mining_100.jsonl"]:
        p = src / fn
        if p.exists():
            shutil.copy2(p, dst / fn)
    _copy_tree(src / "trees", dst / "trees")
    _copy_tree(src / "formula_trees", dst / "formula_trees")

    vf = pd.read_csv(src / "valid_factors.csv")
    vf = vf.sort_values("IC_t", ascending=False).head(gate_count)
    factors = {
        str(r["name"]): (str(r["expression"]), str(r["rationale"]))
        for _, r in vf.iterrows()
    }
    gate_dir, gate_summary = factor_lab.run_report(
        factors,
        outdir=dst / "gate",
        start=sample("start", "1972-01-01"),
        split=sample("split", "2000-12-31"),
        update_library=False,
    )
    passed = int((gate_summary["verdict"] == "PASS").sum()) if len(gate_summary) else 0
    readme = [
        "# LLM mining bundle",
        "",
        f"- Candidate target: {target}",
        f"- Strict-gated candidates: {len(gate_summary)}",
        f"- PASS under strict gate: {passed}",
        "",
        "## Contents",
        "",
        "- `valid_factors.csv` - IC-screened LLM-style candidate set.",
        "- `trees/` - economic derivation trees.",
        "- `formula_trees/` - GP-learning-style formula parse trees.",
        "- `gate/` - per-factor strict gate reports and PNGs, same format as `financing_reversal_guard.png`.",
    ]
    (dst / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(f"LLM mining bundle -> {dst}  gate -> {gate_dir}")
    return dst


def main(full_trials=None, mine_target=100, mined_gate_count=100, min_ic_t=2.0):
    full_trials = full_trials or search("default_full_trials", 300)
    _archive_existing_final()
    FINAL.mkdir(parents=True)
    write_manifest(
        FINAL,
        run_name="consolidated_evaluation",
        params={
            "full_trials": full_trials,
            "start": sample("start", "1972-01-01"),
            "split": sample("split", "2000-12-31"),
            "factor_set": "thesis_core",
            "mine_target": mine_target,
            "mined_gate_count": mined_gate_count,
            "manual_llm_min_ic_t": min_ic_t,
        },
        inputs=default_input_paths(),
        notes="One-shot consolidated evaluation. Previous results/final is archived before refresh.",
    )

    print("\n########## 1. factor_lab (EW/VW + FF ladder) ##########")
    _, fl = factor_lab.run_report(FACTORS, outdir=FINAL / "1_factor_lab")

    print("\n########## 2. spanning ##########")
    spanning.run_spanning({k: v for k, v in EXPRS.items() if k != "prof_trend_ts"},
                          outdir=FINAL / "2_spanning")

    print("\n########## 3. walk-forward ##########")
    walk_forward.run_walk_forward(EXPRS, outdir=FINAL / "3_walk_forward")

    print("\n########## 4. multiple testing ##########")
    multiple_testing.run_haircuts(EXPRS, n_trials=full_trials, outdir=FINAL / "4_multiple_testing")

    print("\n########## 5. horse race (full grammar, GP only) ##########")
    gp_search_full.run_horse_race_full(trials=full_trials, gate=True, do_random=False,
                                       outdir=FINAL / "5_horse_race_full")

    print("\n########## 6. Fama-MacBeth ##########")
    fama_macbeth.run_fama_macbeth(EXPRS, outdir=FINAL / "6_fama_macbeth")

    run_llm_mining_bundle(
        FINAL,
        target=mine_target,
        gate_count=mined_gate_count,
        min_ic_t=min_ic_t,
    )

    print("\n########## summary figure + readme ##########")
    make_summary(FINAL, fl)
    write_readme(FINAL, fl)
    print(f"\nALL DONE -> {FINAL}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-trials", type=int, default=None)
    ap.add_argument("--mine-target", type=int, default=100)
    ap.add_argument("--mined-gate-count", type=int, default=100)
    ap.add_argument("--min-ic-t", type=float, default=2.0)
    args = ap.parse_args()
    main(
        full_trials=args.full_trials,
        mine_target=args.mine_target,
        mined_gate_count=args.mined_gate_count,
        min_ic_t=args.min_ic_t,
    )


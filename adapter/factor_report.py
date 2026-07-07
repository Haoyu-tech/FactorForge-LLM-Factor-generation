# -*- coding: utf-8 -*-
"""Per-factor full report bundle.

For each factor, writes ONE folder containing every artifact:
  results/factor_reports/<factor>/
    <factor>.png             factor_lab 4-panel chart (deciles, cum LS, alphas, IC)
    <factor>.json            full evaluation result (verdict, VW/EW alphas, OOS, checks)
    trees/<factor>.{md,png}          economic derivation tree (hypothesis -> expression)
    formula_trees/<factor>.{md,png}  GP-style formula parse tree

Plus a top-level index.md, summary.csv, and MANIFEST.json.

Run:
  python adapter/factor_report.py                          # default: thesis_extended set
  python adapter/factor_report.py --set thesis_core
  python adapter/factor_report.py --factors mispr_fin_quality mispricing_combo
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()

import factor_lab
from adapter.evaluate_ic import summary as ic_summary
from adapter.manual_llm_mine import write_tree_artifacts
from llm_factor.config import path, sample
from llm_factor.factors import factor_records
from llm_factor.manifest import write_manifest


def _resolve_factors(set_name: str, names: list[str] | None, from_json: str | None) -> list[dict]:
    if from_json:
        data = json.loads(Path(from_json).read_text(encoding="utf-8"))
        factors = data["factors"] if isinstance(data, dict) else data
    else:
        factors = factor_records(set_name)
    if names:
        wanted = set(names)
        factors = [f for f in factors if f["name"] in wanted]
        missing = wanted - {f["name"] for f in factors}
        if missing:
            raise SystemExit(f"factors not found: {sorted(missing)}")
    return factors


def build_one(f: dict, root: Path, start: str, split: str) -> dict:
    name, expr, rationale = f["name"], f["expression"], f.get("rationale", "")
    fdir = root / name
    fdir.mkdir(parents=True, exist_ok=True)

    res = factor_lab.evaluate_factor_full(name, expr, rationale, start=start, split=split)
    factor_lab.plot_factor(dict(res), fdir)                       # writes <name>.png
    json_res = {k: v for k, v in res.items() if k != "_plot"}
    (fdir / f"{name}.json").write_text(
        json.dumps(json_res, indent=2, default=float, ensure_ascii=False), encoding="utf-8")

    # metrics for the tree nodes
    try:
        m = ic_summary(expr, start=start)
    except Exception:
        m = {}
    row = {
        "name": name, "expression": expr, "rationale": rationale,
        "family": f.get("source", ""),
        "IC": m.get("IC", float("nan")), "IC_t": m.get("IC_t", float("nan")),
        "LS_SR": m.get("LS_SR", float("nan")),
    }
    write_tree_artifacts([row], tree_dir=fdir / "trees", formula_tree_dir=fdir / "formula_trees")

    full, test = res["full"], res["test"]
    a6v = (full["vw"]["alphas"] or {}).get("FF5+UMD") or {}
    a6tv = (test["vw"]["alphas"] or {}).get("FF5+UMD") or {}
    return {
        "name": name,
        "verdict": res["verdict"],
        "expression": expr,
        "IC_full": full["IC"], "IC_t_full": full["IC_t"], "mono_full": full["mono"],
        "VW_FF5UMDa_ann": a6v.get("alpha_ann"), "VW_FF5UMDa_t": a6v.get("alpha_t"),
        "IC_test": test["IC"], "VW_FF5UMDa_t_test": a6tv.get("alpha_t"),
        "folder": name,
    }


def main(set_name="thesis_extended", names=None, outdir=None, start=None, split=None, from_json=None) -> None:
    start = start or sample("start", "1972-01-01")
    split = split or sample("split", "2000-12-31")
    root = Path(outdir) if outdir else (path("results_root") / "factor_reports")
    root.mkdir(parents=True, exist_ok=True)
    factors = _resolve_factors(set_name, names, from_json)

    rows = []
    for i, f in enumerate(factors, 1):
        print(f"[{i}/{len(factors)}] {f['name']} ...", flush=True)
        rows.append(build_one(f, root, start, split))
        print(f"    verdict={rows[-1]['verdict']}  VW FF5+UMD a_t={rows[-1]['VW_FF5UMDa_t']:+.2f} "
              f"oos_t={rows[-1]['VW_FF5UMDa_t_test']:+.2f}", flush=True)

    summ = pd.DataFrame(rows).sort_values("VW_FF5UMDa_t", ascending=False)
    summ.to_csv(root / "summary.csv", index=False)

    idx = [f"# Factor reports ({set_name})", "",
           f"Sample {start} .. present; OOS split {split}. One folder per factor with "
           "chart, JSON, derivation tree, and formula tree.", "",
           "| Factor | Verdict | VW FF5+UMD a_t | OOS a_t | Artifacts |", "|---|---|--:|--:|---|"]
    for r in rows:
        n = r["folder"]
        arts = f"[chart]({n}/{n}.png) · [json]({n}/{n}.json) · [tree]({n}/trees/{n}.png) · [formula]({n}/formula_trees/{n}.png)"
        idx.append(f"| {n} | {r['verdict']} | {r['VW_FF5UMDa_t']:+.2f} | {r['VW_FF5UMDa_t_test']:+.2f} | {arts} |")
    (root / "index.md").write_text("\n".join(idx), encoding="utf-8")

    write_manifest(root, run_name=f"factor_reports_{set_name}",
                   params={"set": set_name, "n_factors": len(factors), "start": start, "split": split},
                   notes="Per-factor full report bundles (chart + json + derivation tree + formula tree).")
    n_pass = sum(r["verdict"] == "PASS" for r in rows)
    print(f"\nOUTDIR={root}\nfactors={len(rows)}  PASS={n_pass}  index={root/'index.md'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="set_name", default="thesis_extended")
    ap.add_argument("--factors", nargs="*", default=None)
    ap.add_argument("--from-json", default=None, help="JSON list/{'factors':[...]} of {name,expression,rationale}")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--start", default=None)
    ap.add_argument("--split", default=None)
    args = ap.parse_args()
    main(set_name=args.set_name, names=args.factors, outdir=args.outdir,
         start=args.start, split=args.split, from_json=args.from_json)

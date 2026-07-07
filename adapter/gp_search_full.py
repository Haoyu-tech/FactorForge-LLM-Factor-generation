# -*- coding: utf-8 -*-
"""
FULL-GRAMMAR mechanical search - the strong (un-crippled) baseline for the horse
race. Unlike gp_search.py (signed sums of RANK($field) only), this searches random
EXPRESSION TREES over the SAME operator set the LLM is given: time-series ops
(TS_MEAN/TS_STD/TS_ZSCORE/DELTA/...), cross-sectional normalizers (RANK/ZSCORE/SCALE),
arithmetic (+ - * /), interactions, TS_CORR, and WHERE conditionals.

Each candidate is evaluated with the SAME engine (compute_factor) and the SAME
objective (selection-window mean RankIC) as everything else, then the winner is run
through factor_lab's strict gate (VW / FF5+UMD / OOS). Slower than the narrow search
(no precomputed-rank fast path - every candidate is a real parse+eval), so trials are
in the hundreds, not thousands.

Paper use: report this as the mechanical-search baseline. Random search is kept
behind an explicit CLI flag for ad-hoc diagnostics, but is not part of the default
audit path.

Run:  python adapter/gp_search_full.py --trials 300 --seed 0
"""
import argparse
import json
import random
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from _bootstrap import ensure_project_root
except ImportError:
    from adapter._bootstrap import ensure_project_root
ensure_project_root()
from sp500_loader import compute_factor, load_labels, available_fields
from factor_lab import ROOT
from llm_factor.config import sample, search
from llm_factor.grammar import get_grammar
from llm_factor.ledger import CandidateLedger
from llm_factor.manifest import default_input_paths, run_id, write_manifest
from gp_viz import write_formula_tree, write_lineage_tree


def _fast_rank_ic(f, y):
    """Vectorized mean monthly RankIC (spearman = pearson of within-month ranks)."""
    d = pd.DataFrame({"f": f, "y": y}).dropna()
    if len(d) == 0:
        return None
    k = d.index.get_level_values("datetime").values
    fr = d["f"].groupby(k).rank().to_numpy()
    yr = d["y"].groupby(k).rank().to_numpy()
    df = pd.DataFrame({"k": k, "fr": fr, "yr": yr})
    grp = df.groupby("k")
    fdm = df["fr"] - grp["fr"].transform("mean")
    ydm = df["yr"] - grp["yr"].transform("mean")
    num = (fdm * ydm).groupby(df["k"]).transform("sum")
    den = np.sqrt((fdm ** 2).groupby(df["k"]).transform("sum")
                  * (ydm ** 2).groupby(df["k"]).transform("sum"))
    per_month = pd.DataFrame({"k": df["k"], "ic": num / den}).dropna().drop_duplicates("k")
    return float(per_month["ic"].mean()) if len(per_month) >= 12 else None

# leaves: characteristics + a few price/volume fields (for TS transforms)
class Grammar:
    def __init__(self, seed=0, grammar_name=None):
        self.rng = random.Random(seed)
        self.grammar = get_grammar(grammar_name)
        self.pool = self.grammar.leaf_fields(available_fields())
        self.ts_unary = self.grammar.time_series_unary
        self.cs_unary = self.grammar.cross_sectional_unary
        self.math_unary = self.grammar.math_unary
        self.binary = self.grammar.binary
        self.windows = self.grammar.windows
        if not self.pool:
            raise ValueError(f"grammar '{self.grammar.name}' has no usable leaf fields")

    def leaf(self):
        f = self.rng.choice(self.pool)
        if self.ts_unary and self.windows and self.rng.random() < 0.45:
            op = self.rng.choice(self.ts_unary)
            return f"{op}({f}, {self.rng.choice(self.windows)})"
        return f

    def node(self, depth):
        if depth <= 0 or self.rng.random() < 0.30:
            return self.leaf()
        r = self.rng.random()
        if self.binary and r < 0.40:
            return f"({self.node(depth-1)} {self.rng.choice(self.binary)} {self.node(depth-1)})"
        if self.ts_unary and self.windows and r < 0.70:
            return f"{self.rng.choice(self.ts_unary)}({self.node(depth-1)}, {self.rng.choice(self.windows)})"
        if self.cs_unary and r < 0.88:
            return f"{self.rng.choice(self.cs_unary)}({self.node(depth-1)})"
        if self.math_unary:
            return f"{self.rng.choice(self.math_unary)}({self.node(depth-1)})"
        return self.leaf()

    def component(self, depth=2):
        return f"RANK({self.node(depth)})"           # top-wrap -> cross-sectionally comparable

    def candidate(self, depth=2):
        k = self.rng.randint(1, self.grammar.max_terms)
        return [(self.rng.choice([1, -1]), self.component(depth)) for _ in range(k)]


def cand_expr(cand):
    parts = [("+" if s > 0 else "-") + c for s, c in cand]
    e = " ".join(parts)
    return e[1:].strip() if e.startswith("+") else e.strip()


class Scorer:
    def __init__(self, start=None, split=None, ledger=None, run_id=None):
        start = start or sample("start", "1972-01-01")
        split = split or sample("split", "2000-12-31")
        self.start, self.split = pd.Timestamp(start), pd.Timestamp(split)
        self.label = load_labels()
        self.cache = {}
        self.ledger = ledger
        self.run_id = run_id

    def _record(self, expr, window, status, source="gp_full", **extra):
        if self.ledger is None:
            return
        self.ledger.append(
            run_id=self.run_id,
            source=source,
            window=window,
            status=status,
            expression=expr,
            **extra,
        )

    def _ic(self, expr, window, source="gp_full"):
        try:
            f = compute_factor(expr).replace([np.inf, -np.inf], np.nan)
        except Exception as exc:
            self._record(expr, window, "error", source=source, error=str(exc))
            return None
        if f.notna().mean() < 0.30 or f.std(skipna=True) == 0:
            self._record(
                expr,
                window,
                "invalid",
                source=source,
                reason="low_coverage_or_constant",
                coverage=float(f.notna().mean()),
            )
            return None
        dt = f.index.get_level_values("datetime")
        if window == "sel":
            m = (dt >= self.start) & (dt <= self.split)
        elif window == "oos":
            m = dt > self.split
        else:
            m = dt >= self.start
        y = self.label.reindex(f.index)
        ic = _fast_rank_ic(f[m], y[m])
        if ic is None:
            self._record(expr, window, "invalid", source=source, reason="insufficient_monthly_ic")
        else:
            self._record(
                expr,
                window,
                "accepted",
                source=source,
                metrics={"mean_rank_ic": ic, "coverage": float(f.notna().mean())},
            )
        return ic

    def sel(self, expr, source="gp_full"):
        if expr not in self.cache:
            self.cache[expr] = self._ic(expr, "sel", source=source)
        else:
            cached = self.cache[expr]
            self._record(
                expr,
                "sel",
                "cached",
                source=source,
                metrics={"mean_rank_ic": cached} if cached is not None else {},
            )
        return self.cache[expr]

    def oos(self, expr, source="gp_full"):
        return self._ic(expr, "oos", source=source)


def _signed(cand, ic):
    if ic is not None and ic < 0:
        return [(-s, c) for s, c in cand], -ic
    return cand, (abs(ic) if ic is not None else None)


def random_search(gram, scorer, n_trials, depth=2):
    best, hist, seen = None, [], set()
    i = 0
    while i < n_trials:
        cand = gram.candidate(depth)
        expr = cand_expr(cand)
        if expr in seen:
            continue
        seen.add(expr); i += 1
        ic = scorer.sel(expr)
        if ic is None:
            hist.append((i, best[1] if best else 0.0)); continue
        cand, aic = _signed(cand, ic)
        if best is None or aic > best[1]:
            best = (cand, aic)
        hist.append((i, best[1]))
        if i % 25 == 0:
            print(f"   [random] {i}/{n_trials}  best sel_IC={best[1]:+.4f}", flush=True)
    return best, hist


def genetic_search(gram, scorer, pop_size=30, gens=10, depth=2, viz_dir=None):
    rng = gram.rng
    lineage = []
    node_counter = 0

    def new_node(cand, gen, op, parents, score=None):
        nonlocal node_counter
        node_counter += 1
        nid = f"G{gen}_{node_counter:04d}"
        lineage.append({
            "id": nid,
            "gen": gen,
            "op": op,
            "parents": list(parents),
            "expr": cand_expr(cand),
            "score": score,
        })
        return nid

    def set_score(nid, score):
        for r in lineage:
            if r["id"] == nid:
                r["score"] = score
                return

    def fit(cand):
        ic = scorer.sel(cand_expr(cand))
        return abs(ic) if ic is not None else -1.0

    pop = []
    for _ in range(pop_size):
        c = gram.candidate(depth)
        nid = new_node(c, 0, "init", [])
        s = fit(c)
        set_score(nid, s)
        pop.append((nid, c, s))
    scored = list(pop)
    best = max(scored, key=lambda x: x[2]); evals = pop_size
    hist = [(evals, best[2])]

    def mutate(cand):
        cand = list(cand)
        op = rng.random()
        if op < 0.4 and cand:                         # regenerate one component's subtree
            i = rng.randrange(len(cand)); cand[i] = (cand[i][0], gram.component(depth))
        elif op < 0.6 and cand:                       # flip a sign
            i = rng.randrange(len(cand)); cand[i] = (-cand[i][0], cand[i][1])
        elif op < 0.8 and len(cand) < 3:              # add a component
            cand.append((rng.choice([1, -1]), gram.component(depth)))
        elif len(cand) > 1:                           # drop a component
            cand.pop(rng.randrange(len(cand)))
        return cand

    def crossover(a, b):
        items = list(a) + list(b)
        rng.shuffle(items)
        return items[: rng.randint(1, 3)]

    for gen in range(1, gens + 1):
        scored.sort(key=lambda x: x[2], reverse=True)
        elite = scored[: max(2, pop_size // 5)]
        children = list(elite)
        while len(children) < pop_size:
            if rng.random() < 0.6 and len(elite) > 1:
                p1, p2 = rng.sample(elite, 2)
                child = mutate(crossover(p1[1], p2[1]))
                children.append((new_node(child, gen, "crossover+mutate", [p1[0], p2[0]]), child, None))
            else:
                p = rng.choice(elite)
                child = mutate(p[1])
                children.append((new_node(child, gen, "mutate", [p[0]]), child, None))
        rescored = []
        for nid, c, s in children:
            if s is None:
                s = fit(c)
                set_score(nid, s)
            rescored.append((nid, c, s))
        scored = rescored
        evals += len(children)
        gb = max(scored, key=lambda x: x[2])
        if gb[2] > best[2]:
            best = gb
        hist.append((evals, best[2]))
        print(f"   [gp] evals={evals}  best sel_IC={best[2]:+.4f}", flush=True)
    cand, aic = _signed(best[1], scorer.sel(cand_expr(best[1])))
    best_expr = cand_expr(cand)
    for r in lineage:
        r["is_best"] = r["id"] == best[0]
    if viz_dir is not None:
        viz_dir.mkdir(parents=True, exist_ok=True)
        write_lineage_tree(lineage, viz_dir / "lineage_tree.md", viz_dir / "lineage_tree.png",
                           title="Full GP Evolution Lineage")
        write_formula_tree(best_expr, viz_dir / "winner_formula_tree.md", viz_dir / "winner_formula_tree.png",
                           title="GP Winner Formula Parse Tree")
        (viz_dir / "lineage_records.json").write_text(json.dumps(lineage, indent=2), encoding="utf-8")
    return (cand, aic), hist, lineage


# LLM reference = the full-chain survivors the LLM generated from the expanded 120-factor pool.
LLM_FACTORS = {
    "cash_prof_accrual_quality": "RANK($cop_at) - RANK($oaccruals_at) - RANK($eqnetis_at)",
    "quality_bloat_value": "RANK($qmj_prof) + RANK($qmj_safety) + RANK($sale_me) - RANK($noa_at)",
    "shareholder_yield_quality": "RANK($eqnpo_me) + RANK($cop_at) - RANK($eqnetis_at)",
    "earnings_yield_stability": "RANK($ni_me / ($ni_ivol + 1)) + RANK($cop_at)",
    "persistent_mispricing_disc": "RANK(TS_MEAN($mispricing_perf, 6) + TS_MEAN($mispricing_mgmt, 6)) - RANK(TS_MEAN($eqnetis_at, 12))",
}


def run_horse_race_full(trials=None, seed=None, depth=2, start=None,
                        split=None, gate=True, outdir=None, do_random=False, grammar_name=None):
    trials = trials or search("default_full_trials", 300)
    seed = search("default_seed", 0) if seed is None else seed
    start = start or sample("start", "1972-01-01")
    split = split or sample("split", "2000-12-31")
    outdir = Path(outdir) if outdir else ROOT / "results" / f"horserace_full_{datetime.now():%Y%m%d_%H%M%S}"
    outdir.mkdir(parents=True, exist_ok=True)
    rid = run_id("gp_full")
    ledger = CandidateLedger(rid)
    grammar_name = grammar_name or search("primary_grammar", "fast_full")
    gram = Grammar(seed, grammar_name=grammar_name)
    scorer = Scorer(start, split, ledger=ledger, run_id=rid)
    print(f"pool={len(gram.pool)} leaves  grammar={gram.grammar.name} (depth {depth})  selection={start}..{split}")
    print(f"candidate ledger -> {ledger.path}")

    print("\n== LLM factors ==")
    llm = {}
    for nm, e in LLM_FACTORS.items():
        s, o = scorer.sel(e, source="llm_reference"), scorer.oos(e, source="llm_reference")
        llm[nm] = (s, o)
        print(f"  {nm:18} sel_IC={s:+.4f}  OOS_IC={o:+.4f}")
    llm_best = max(v[0] for v in llm.values())

    def reach(hist, tgt):
        for t, b in hist:
            if b >= tgt:
                return t
        return None

    rc = ric = rt = None
    if do_random:
        print(f"\n== random search (full grammar, {trials} trials) ==")
        (rc, ric), rhist = random_search(gram, scorer, trials, depth)
        print(f"  best sel_IC={ric:+.4f}  OOS_IC={scorer.oos(cand_expr(rc)):+.4f}\n   {cand_expr(rc)}")
        pd.DataFrame(rhist, columns=["trial", "best_sel_IC"]).to_csv(outdir / "random_curve.csv", index=False)
        rt = reach(rhist, llm_best)

    pop = min(30, max(6, trials)); gens = max(1, trials // pop)   # scale GP with the trial budget
    print(f"\n== genetic search (full grammar, pop={pop} x {gens+1} ~ {pop*(gens+1)} evals) ==")
    gp_viz_dir = outdir / "gp_trees"
    (gc, gic), ghist, lineage = genetic_search(gram, scorer, pop, gens, depth, viz_dir=gp_viz_dir)
    print(f"  best sel_IC={gic:+.4f}  OOS_IC={scorer.oos(cand_expr(gc)):+.4f}\n   {cand_expr(gc)}")
    pd.DataFrame(ghist, columns=["evals", "best_sel_IC"]).to_csv(outdir / "gp_curve.csv", index=False)
    gt = reach(ghist, llm_best)

    L = ["# Horse race (FULL GRAMMAR): LLM vs strong mechanical search",
         f"_Expression trees over the full operator set (depth {depth}), same engine "
         f"(compute_factor), same objective (selection RankIC {start}..{split}), same OOS (>{split}). "
         f"LLM best selection IC = {llm_best:+.4f}._\n",
         "## LLM factors", "", "| Factor | sel IC | OOS IC |", "|---|---|---|"]
    for nm, (s, o) in llm.items():
        L.append(f"| {nm} | {s:+.4f} | {o:+.4f} |")
    L += ["", "## Search winners", "",
          "| Method | best sel IC | OOS IC | trials to LLM-best sel IC | expression |",
          "|---|---|---|---|---|"]
    if do_random:
        L.append(f"| Random (full) | {ric:+.4f} | {scorer.oos(cand_expr(rc)):+.4f} | {rt or '>'+str(trials)} | `{cand_expr(rc)}` |")
    L.append(f"| Genetic (full) | {gic:+.4f} | {scorer.oos(cand_expr(gc)):+.4f} | {gt or '>'+str(ghist[-1][0])} | `{cand_expr(gc)}` |")
    (outdir / "horse_race_full.md").write_text("\n".join(L), encoding="utf-8")
    if do_random:
        print(f"\nLLM best sel_IC={llm_best:+.4f} | random reached it in {rt}, GP in {gt}")
    else:
        print(f"\nLLM best sel_IC={llm_best:+.4f} | GP reached it in {gt}")
    write_manifest(
        outdir,
        run_name=rid,
        params={
            "method": "gp_full",
            "trials": trials,
            "seed": seed,
            "depth": depth,
            "operator_grammar": gram.grammar.name,
            "start": start,
            "split": split,
            "do_random": do_random,
            "candidate_ledger": str(ledger.path),
            "gp_tree_dir": str(gp_viz_dir),
            "gp_lineage_nodes": len(lineage),
        },
        inputs={**default_input_paths(), "candidate_ledger": ledger.path},
        notes="Full-grammar GP search. Random search is disabled by default.",
    )

    if gate:                                          # the punchline: winners through the strict gate
        from factor_lab import run_report
        winners = {"GPfull_winner": (cand_expr(gc),
                   "Full-grammar GP search winner (no economic prior). Tests whether a strong, "
                   "expressive mechanical search survives the strict gate (VW / FF5+UMD / OOS).")}
        if do_random:
            winners["RANDfull_winner"] = (cand_expr(rc), "Full-grammar random-search winner (no economic prior).")
        print("\n== winners through strict gate (VW / FF5+UMD / OOS) ==")
        run_report(winners, outdir=str(outdir / "gate"), start=start, split=split, update_library=False)
    print(f"\nfull-grammar horse-race -> {outdir}")
    return outdir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--grammar", default=None, help="operator grammar name from configs/llm_factor.json")
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--with-random", action="store_true", help="also run the deprecated random-search baseline")
    args = ap.parse_args()
    run_horse_race_full(trials=args.trials, seed=args.seed, depth=args.depth,
                        gate=not args.no_gate, do_random=args.with_random,
                        grammar_name=args.grammar)


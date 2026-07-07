# -*- coding: utf-8 -*-
"""
Narrow genetic-programming baseline for the horse race against LLM factor
synthesis. Random search is kept behind an explicit diagnostic flag, but is not
part of the default audit path.

Both search the SAME factor language the LLM uses - signed sums of cross-sectional
ranks, sum_i s_i * RANK($field_i), 2-4 distinct fields - and are scored by the
SAME objective (mean monthly RankIC on a selection window). This isolates the one
thing under test: does the LLM's economic prior find good, OOS-robust factors in
far fewer trials than blind search?

Speed: cross-sectional ranks of every field are precomputed once, so a candidate's
IC is a vectorized monthly correlation - thousands of trials in seconds. The winner
is then handed to factor_lab for the full asset-pricing gate (VW / FF5+UMD / OOS).

Run:  python adapter/gp_search.py --trials 600 --seed 0
"""
import argparse
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
from sp500_loader import load_features, load_labels, available_fields
from factor_lab import ROOT
from llm_factor.config import sample, search
from llm_factor.grammar import get_grammar
from llm_factor.ledger import CandidateLedger
from llm_factor.manifest import default_input_paths, run_id, write_manifest


class FastIC:
    """Precomputed cross-sectional ranks -> vectorized monthly RankIC on a window."""

    def __init__(self, start=None, split=None, ledger=None, run_id=None):
        start = start or sample("start", "1972-01-01")
        split = split or sample("split", "2000-12-31")
        feats = load_features()
        self.grammar = get_grammar("rank_sum")
        pool = self.grammar.leaf_fields(available_fields())
        self.pool = pool
        lab = load_labels().reindex(feats.index)
        dt = feats.index.get_level_values("datetime")
        self.dt = dt
        # cross-sectional percentile ranks; missing char -> neutral 0.5
        R = feats[pool].groupby(level="datetime").rank(pct=True).fillna(0.5)
        Lr = lab.groupby(level="datetime").rank(pct=True)
        keep = Lr.notna().values                     # need a forward return
        self.R = R[keep]
        self.Lr = Lr[keep]
        self.dt = dt[keep]
        self._masks = {
            "sel": (self.dt >= pd.Timestamp(start)) & (self.dt <= pd.Timestamp(split)),
            "oos": self.dt > pd.Timestamp(split),
            "full": self.dt >= pd.Timestamp(start),
        }
        self.ledger = ledger
        self.run_id = run_id
        # store grouping keys + demeaned-label denominator per window
        self._win = {}
        for w, m in self._masks.items():
            dtw = pd.Series(self.dt[m])
            lr = self.Lr[m].reset_index(drop=True)
            lr_dm = lr - lr.groupby(dtw.values).transform("mean")
            denomL = (lr_dm ** 2).groupby(dtw.values).transform("sum")
            self._win[w] = {"key": dtw.values, "lr_dm": lr_dm.values,
                            "denomL": denomL.values, "R": self.R[m].reset_index(drop=True)}

    def ic(self, weights: dict, window="sel", source="gp_rank_sum"):
        """Mean monthly RankIC of sum_i w_i*rank(field_i) vs forward return."""
        W = self._win[window]
        f = np.zeros(len(W["key"]))
        for fld, s in weights.items():
            f += s * W["R"][fld].values
        key = W["key"]
        s = pd.Series(f)
        f_dm = (s - s.groupby(key).transform("mean")).values
        num = pd.Series(f_dm * W["lr_dm"]).groupby(key).transform("sum").values
        denF = pd.Series(f_dm ** 2).groupby(key).transform("sum").values
        denom = np.sqrt(denF * W["denomL"])
        with np.errstate(invalid="ignore", divide="ignore"):
            ic_row = np.where(denom > 0, num / denom, np.nan)
        # one value per month: take first row per group
        tmp = pd.DataFrame({"key": key, "ic": ic_row}).dropna().drop_duplicates("key")
        val = float(tmp["ic"].mean())
        if self.ledger:
            self.ledger.append(
                run_id=self.run_id,
                source=source,
                window=window,
                status="accepted" if val == val else "invalid",
                expression=_expr(weights),
                weights=weights,
                metrics={"mean_rank_ic": val},
            )
        return val


def _expr(weights: dict) -> str:
    parts = []
    for f, s in weights.items():
        parts.append(("+" if s > 0 else "-") + f"RANK({f})")
    e = " ".join(parts)
    return e[1:].strip() if e.startswith("+") else e.strip()


def _signed(weights, ic):
    """Flip all signs so the reported factor has positive IC."""
    if ic < 0:
        return {f: -s for f, s in weights.items()}, -ic
    return weights, ic


def _rand_cand(pool, rng, kmin=2, kmax=4):
    k = rng.randint(kmin, kmax)
    fields = rng.sample(pool, k)
    return {f: rng.choice([1, -1]) for f in fields}


def random_search(fic, n_trials, seed=0):
    rng = random.Random(seed)
    best, hist, seen = None, [], set()
    for i in range(1, n_trials + 1):
        c = _rand_cand(fic.pool, rng)
        kkey = tuple(sorted(c.items()))
        if kkey in seen:
            continue
        seen.add(kkey)
        ic = fic.ic(c, "sel", source="random_deprecated")
        c, aic = _signed(c, ic)
        if best is None or aic > best[1]:
            best = (c, aic)
        hist.append((i, best[1]))
    return best, hist


def genetic_search(fic, pop_size=40, gens=15, seed=0):
    rng = random.Random(seed)
    pool = fic.pool

    def fit(c):
        ic = fic.ic(c, "sel", source="gp_rank_sum")
        return abs(ic)

    pop = [_rand_cand(pool, rng) for _ in range(pop_size)]
    scored = [(c, fit(c)) for c in pop]
    best, hist, evals = max(scored, key=lambda x: x[1]), [], pop_size

    def mutate(c):
        c = dict(c)
        op = rng.random()
        if op < 0.4 and c:                            # flip a sign
            f = rng.choice(list(c)); c[f] = -c[f]
        elif op < 0.7 and c:                          # swap a field
            f = rng.choice(list(c)); del c[f]
            nf = rng.choice([x for x in pool if x not in c])
            c[nf] = rng.choice([1, -1])
        elif op < 0.85 and len(c) < 4:                # add a term
            nf = rng.choice([x for x in pool if x not in c])
            c[nf] = rng.choice([1, -1])
        elif len(c) > 2:                              # drop a term
            del c[rng.choice(list(c))]
        return c

    def crossover(a, b):
        items = list(a.items()) + [(f, s) for f, s in b.items() if f not in a]
        rng.shuffle(items)
        k = rng.randint(2, 4)
        return dict(items[:k])

    hist.append((evals, best[1]))
    for _ in range(gens):
        scored.sort(key=lambda x: x[1], reverse=True)
        elite = [c for c, _ in scored[: max(2, pop_size // 5)]]
        children = list(elite)
        while len(children) < pop_size:
            if rng.random() < 0.6:
                a, b = rng.sample(elite, 2) if len(elite) > 1 else (elite[0], elite[0])
                children.append(mutate(crossover(a, b)))
            else:
                children.append(mutate(rng.choice(elite)))
        scored = [(c, fit(c)) for c in children]
        evals += len(children)
        gbest = max(scored, key=lambda x: x[1])
        if gbest[1] > best[1]:
            best = gbest
        hist.append((evals, best[1]))
    c, aic = _signed(best[0], fic.ic(best[0], "sel", source="gp_rank_sum"))
    return (c, aic), hist


# LLM factors expressed as the same signed-rank dicts (for an apples-to-apples axis)
LLM_FACTORS = {
    "mispricing_combo": {"$mispricing_perf": 1, "$mispricing_mgmt": 1},
    "mispr_fin_disc": {"$mispricing_perf": 1, "$mispricing_mgmt": 1, "$eqnetis_at": -1, "$at_gr1": -1},
    "qual_val_mom": {"$gp_at": 1, "$be_me": 1, "$ret_12_1": 1},
}


def run_horse_race(trials=None, seed=None, start=None, split=None, outdir=None, do_random=False):
    trials = trials or search("default_full_trials", 300)
    seed = search("default_seed", 0) if seed is None else seed
    start = start or sample("start", "1972-01-01")
    split = split or sample("split", "2000-12-31")
    outdir = Path(outdir) if outdir else ROOT / "results" / f"horserace_{datetime.now():%Y%m%d_%H%M%S}"
    outdir.mkdir(parents=True, exist_ok=True)
    rid = run_id("gp_rank_sum")
    ledger = CandidateLedger(rid)
    fic = FastIC(start, split, ledger=ledger, run_id=rid)
    print(f"pool={len(fic.pool)} fields  selection={start}..{split}  OOS>{split}")
    print(f"operator grammar -> {fic.grammar.name}")
    print(f"candidate ledger -> {ledger.path}")

    # LLM factors on the same axis
    print("\n== LLM factors (economic prior) ==")
    llm = {}
    for nm, c in LLM_FACTORS.items():
        sel, oos = fic.ic(c, "sel", source="llm_reference"), fic.ic(c, "oos", source="llm_reference")
        llm[nm] = (sel, oos)
        print(f"  {nm:18} sel_IC={sel:+.4f}  OOS_IC={oos:+.4f}  {_expr(c)}")

    rc = ric = rhist = rt = None
    if do_random:
        print(f"\n== random search ({trials} trials) ==")
        (rc, ric), rhist = random_search(fic, trials, seed)
        print(f"  best sel_IC={ric:+.4f}  OOS_IC={fic.ic(rc,'oos', source='random_deprecated'):+.4f}  {_expr(rc)}")

    print(f"\n== genetic search (~{trials} evals) ==")
    pop = min(40, max(6, trials))
    gens = max(1, trials // pop)
    (gc, gic), ghist = genetic_search(fic, pop, gens, seed)
    print(f"  best sel_IC={gic:+.4f}  OOS_IC={fic.ic(gc,'oos'):+.4f}  {_expr(gc)}")

    # learning curve: trials needed to reach the best LLM selection-IC
    llm_best_sel = max(v[0] for v in llm.values())
    def trials_to(hist, target):
        for t, b in hist:
            if b >= target:
                return t
        return None
    rt = trials_to(rhist, llm_best_sel) if rhist else None
    gt = trials_to(ghist, llm_best_sel)

    # write learning curve + summary
    if do_random:
        pd.DataFrame(rhist, columns=["trial", "best_sel_IC"]).to_csv(outdir / "random_curve.csv", index=False)
    pd.DataFrame(ghist, columns=["evals", "best_sel_IC"]).to_csv(outdir / "gp_curve.csv", index=False)

    L = ["# Horse race: LLM vs mechanical search",
         f"_Same factor language (signed sums of RANK($field), 2-4 terms), same objective "
         f"(selection-window mean RankIC, {start}..{split}), same OOS (>{split}). "
         f"LLM best selection IC = {llm_best_sel:+.4f}._\n",
         "## LLM factors (economic prior)", "",
         "| Factor | sel IC | OOS IC | expression |", "|---|---|---|---|"]
    for nm, (s, o) in llm.items():
        L.append(f"| {nm} | {s:+.4f} | {o:+.4f} | `{_expr(LLM_FACTORS[nm])}` |")
    L += ["", "## Search winners", "",
          "| Method | best sel IC | OOS IC | trials to reach LLM-best sel IC | expression |",
          "|---|---|---|---|---|"]
    if do_random:
        L.append(f"| Random (deprecated) | {ric:+.4f} | {fic.ic(rc,'oos', source='random_deprecated'):+.4f} | {rt if rt else '>'+str(trials)} | `{_expr(rc)}` |")
    L.append(f"| Genetic | {gic:+.4f} | {fic.ic(gc,'oos', source='gp_rank_sum'):+.4f} | {gt if gt else '>'+str(len(ghist) and ghist[-1][0])} | `{_expr(gc)}` |")
    (outdir / "horse_race.md").write_text("\n".join(L), encoding="utf-8")
    if do_random:
        print(f"\nLLM best sel_IC={llm_best_sel:+.4f} | random reached it in {rt} trials, GP in {gt} evals")
    else:
        print(f"\nLLM best sel_IC={llm_best_sel:+.4f} | GP reached it in {gt} evals")
    write_manifest(
        outdir,
        run_name=rid,
        params={
            "method": "gp_rank_sum",
            "operator_grammar": fic.grammar.name,
            "trials": trials,
            "seed": seed,
            "start": start,
            "split": split,
            "do_random": do_random,
            "candidate_ledger": str(ledger.path),
        },
        inputs={**default_input_paths(), "candidate_ledger": ledger.path},
        notes="Narrow signed-rank GP search. Random search is disabled by default.",
    )
    print(f"horse-race -> {outdir}")
    return outdir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--with-random", action="store_true", help="also run the deprecated random-search diagnostic")
    args = ap.parse_args()
    run_horse_race(trials=args.trials, seed=args.seed, do_random=args.with_random)


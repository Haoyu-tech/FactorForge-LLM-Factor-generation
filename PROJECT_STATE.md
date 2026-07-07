# LLM-Factor State Structure

This project separates four kinds of research state:

1. Configuration state
   - `configs/llm_factor.json`
   - Machine-specific paths, sample splits, evaluation thresholds, and search defaults.
   - Override external paths with environment variables instead of editing scripts.
   - Operator grammars live here too. The main LLM-vs-GP comparison uses the
     shared `fast_full` grammar; `rank_sum` is a narrow transparent baseline and
     `full_llm` is reserved for appendix-style LLM-only experiments.

2. Hypothesis state
   - `configs/factors.json`
   - Curated factor names, expressions, rationales, and sources.
   - Adapter scripts import this registry instead of copying `DEFAULT_FACTORS`.

3. Candidate state
   - `results/candidate_ledgers/*.jsonl`
   - Append-only record of every LLM/search candidate, including duplicates, parse errors,
     missing rationales, insufficient data, and accepted factors.
   - `adapter/run_sp500.py` records LLM candidates; `adapter/gp_search_full.py`
     records full-grammar GP candidates. Random search is not part of the default
     audit path.
   - Manual LLM mining progress and factor derivation trees are kept under
     `results/manual_llm_mining_100/`; each valid factor has a Mermaid `.md`
     tree and a rendered `.png` tree in `results/manual_llm_mining_100/trees/`.
   - LLM factor formulas also have GP-learning-style parse trees in
     `results/manual_llm_mining_100/formula_trees/`: blue oval operator/field
     node diagrams plus Mermaid `.md` files for every valid factor.
   - Full-GP runs now write GP-style visual artifacts under each run's `gp_trees/`
     folder: `lineage_tree.{md,png}` for mutation/crossover ancestry,
     `winner_formula_tree.{md,png}` for formula-operator decomposition, and
     `lineage_records.json` for machine-readable evolution records.
   - This is the audit trail for researcher degrees of freedom.

4. Run state
   - `results/final/MANIFEST.json` for the consolidated run.
   - `results/archive/final_<timestamp>/` for previous final outputs.
   - Per-run output folders can also carry `MANIFEST.json`, with config, parameters,
     input file fingerprints, runtime environment, and optional candidate ledger paths.

## LLM discovery prompt policy (standing rule)

The LLM discovery prompt (`adapter/scenario_sp500.md` + the lines appended by
`adapter/run_sp500.py`) must contain exactly three things and nothing else:

1. **Data / rules description** — universe, monthly frequency, label, and the rules
   for a valid expression (one expression, cross-sectionally comparable, no look-ahead).
2. **Field list** — the authoritative `$`-field pool, which is `grammar.leaf_fields`
   (identical to the GP leaf pool, for a fair LLM-vs-GP comparison).
3. **Operator glossary** — the appended `PRIMARY OPERATOR GRAMMAR` / `OPERATORS:` line
   (operator names only, same source GP uses).

**No worked/example factor expressions.** Do not embed any complete factor (e.g.
`RANK($x) - RANK($y)`), and do not report any in-sample performance (no "IC t≈…").
Reasons: worked examples (a) leak which fields/factors win on this panel into the
prompt and (b) anchor the LLM's structure and mechanism, both of which are
data-snooping / researcher-degrees-of-freedom attack surfaces. Operator-glossary
snippets that use a placeholder like `A` (e.g. `TS_MEAN(A, 12)`) are allowed — they
define syntax, they are not factors. This mirrors QuantaAlpha's own prompt form.

This is the frozen convention: any future edit to the discovery prompt keeps these
three parts and adds no example factors.

Recommended flow:

```text
raw WRDS files
  -> data/*.parquet
  -> configs/factors.json or LLM candidate ledger
  -> adapter/factor_lab.py / spanning.py / walk_forward.py / ...
  -> results/<run>/ + MANIFEST.json
  -> results/final/ for the current paper tables
```

The adapter scripts remain runnable by file path, for example:

```powershell
python adapter\smoke_test_kelly.py
python adapter\run_all.py --full-trials 300
```

When passing expressions containing `$` in PowerShell, use single quotes:

```powershell
python adapter\evaluate_ic.py '$ret_12_1'
```

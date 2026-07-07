# LLM Factor Generation Protocol

This protocol fixes the factor-generation design before any new OOS results are
used. Its purpose is to make the paper read as an auditable economic hypothesis
generation study, not as a winner-picking exercise.

## Research Claim

Large language models are used as economic hypothesis generators for empirical
asset pricing. They propose interpretable, grammar-valid factor expressions that
are then evaluated by a pre-specified asset-pricing pipeline.

The LLM is not allowed to tune on OOS performance.

## Model Design

Use three LLMs:

| Role | Count | Candidate budget | Purpose |
|---|---:|---:|---|
| Primary model | 1 | 30-50 | Headline LLM factor-generation result |
| Robustness models | 2 | 30 each | Show the result is not model-specific |

The primary paper tables should identify the primary model in advance. The two
robustness models are reported at the model level and cannot replace the primary
model after OOS results are observed.

For every model, record:

| Field | Requirement |
|---|---|
| model_name | Exact API model identifier |
| provider | API provider or local backend |
| prompt_version | Hash or version name of the prompt |
| grammar | `fast_full` unless explicitly marked appendix-only |
| candidate_budget | Maximum attempted candidates |
| valid_candidates | Parsed and evaluable expressions |
| failed_candidates | Parse errors, duplicate expressions, missing fields, or no rationale |
| selection_metric | Discovery-period metric only |

## Sample Split

| Window | Dates | Use |
|---|---|---|
| Discovery | 1972-07-01 to 2000-12-31 | Generate feedback and select candidates |
| OOS | 2001-01-01 to sample end | Locked validation only |
| Walk-forward | Starts 1990-01-01 in 3-year blocks | Stability robustness |

OOS results must not be shown to the LLM during candidate generation, prompt
revision, or factor selection.

## Candidate Rules

Every generated factor must include:

| Item | Rule |
|---|---|
| name | Stable snake_case identifier |
| expression | Grammar-valid expression over approved fields |
| rationale | Economic mechanism stated before OOS evaluation |
| source | `llm:<model_name>` or `baseline:<method>` |
| timestamp | Run timestamp |
| status | accepted, duplicate, parse_error, insufficient_data, or failed_gate |

The candidate ledger is append-only. Failed candidates stay in the ledger.

## Selection Rule

Selection happens only on the discovery window.

Primary selection metrics:

1. Valid expression and non-empty economic rationale.
2. Positive discovery RankIC.
3. Discovery value-weighted FF5+UMD alpha or RankIC ranking, depending on the
   pre-registered run setting.
4. No use of post-2000 OOS alpha, OOS IC, or walk-forward results.

After selection, all reported factors go through the same final pipeline:

1. Full-sample portfolio sorts.
2. OOS portfolio sorts.
3. FF5+UMD alpha.
4. Spanning against components and the Kelly anomaly zoo.
5. Walk-forward stability.
6. Fama-MacBeth regressions.
7. Multiple-testing haircuts using the full attempted candidate budget.

## Baseline

The main paper baseline is full-grammar GP search. Random grammar search is an
optional appendix diagnostic, not part of the main design.

| Baseline | Purpose |
|---|---|
| Full-grammar GP search | Strong mechanical symbolic-search benchmark |
| Random grammar search | Optional appendix diagnostic |

The GP baseline uses the same parser, approved field list, sample split, and
candidate budget accounting as the LLMs.

## Reporting Standard

The paper should report:

| Table | Content |
|---|---|
| Candidate accounting | Attempts, valid expressions, duplicates, failures, selected factors |
| Main performance | VW long-short and FF5+UMD alpha, full sample and OOS |
| Model robustness | Per-LLM pass rate, average OOS IC, best selected OOS alpha |
| Baseline comparison | LLM vs budget-matched GP search |
| Audit appendix | Prompt version, grammar, ledger path, and manifest |

The headline contribution should be phrased as:

> LLMs provide an auditable economic hypothesis-generation layer for asset
> pricing factor discovery, and their proposed factors survive pre-specified
> empirical validation better than matched GP search.

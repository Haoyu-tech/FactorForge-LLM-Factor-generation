# Run Database Design

**Date:** 2026-11-15
**Status:** Approved, pending implementation
**Component:** `factorforge/frontend-v2/backend/`, `factorforge/quantaalpha/pipeline/`

## Purpose

Persist what each pipeline run was, what it cost, and what it produced, so that:

1. **Research evidence.** Each run is an experiment observation. The database must answer
   questions like "does `opus` find better factors than `sonnet`, and is the extra spend
   justified?" That requires joining runs to the factors they produced, with cost
   attributable per model.
2. **Cost and usage tracking.** Know what a run cost, broken down by model, channel and
   pipeline stage, and what has been spent over a period.

Both goals are served by one schema. Nothing else is in scope.

## Problem

Run metadata lives only in the backend's in-memory `tasks` dict (`app.py:208`). Every
restart erases it. This is not hypothetical: it happened twice on 2026-11-15, once
losing a completed run's record and once losing an in-flight run's history.

The durable artifacts that survive today are disconnected from each other:

| Artifact | Location | Holds |
|---|---|---|
| Run logs | `log/exp_YYYYMMDD_HHMMSS/` | `evolution_state.json`, `trajectory_pool.json` |
| Factor library | `data/factorlib/all_factors_library_*.json` | factors with metrics and metadata |
| Pickle caches | `data/results/pickle_cache_exp_*/` | intermediate evaluation state |

`experiment_id` is the thread tying these together, but nothing records what the run
*was* — which model served it, how it was reached, what it cost, how long it took.

## Blocking prerequisite: the factor-to-run join key is broken

**This must be fixed before the database has value.** Measured on 2026-11-15, 59 of 65
factors across all libraries carry `metadata.experiment_id == "unknown"`. Only 6 are
attributable, and they come from just two runs (`exp_20261114_074849`,
`exp_20261115_185559`). These counts grow with every run; the ratio is the point, not the
absolute numbers.

Two code paths write factors to the library:

- `quantaalpha/pipeline/loop.py:222` uses `os.environ.get("EXPERIMENT_ID", "unknown")`.
  This is correct; `app.py` sets `env["EXPERIMENT_ID"]` before launching the subprocess.
- `quantaalpha/pipeline/loop.py:254`, inside `feedback()`, which saves most factors,
  initialises `experiment_id = "unknown"` and then tries to recover it from
  `self.session_folder` by finding a path component where `part.startswith("202")`.

The backend's experiment ids have the form `exp_20261115_203926`. They start with `exp`,
not `202`, so the scan never matches and the id stays `"unknown"`.

### Fix

In `loop.py`, inside `feedback()`, prefer the environment variable and widen the fallback:

```python
experiment_id = os.environ.get("EXPERIMENT_ID") or "unknown"
if experiment_id == "unknown" and getattr(self, "session_folder", None):
    for part in Path(self.session_folder).parts:
        if part.startswith("exp_") or part.startswith("202"):
            experiment_id = part
            break
```

This is a prerequisite task, not a follow-up. Without it every future factor remains
unattributable and the research purpose fails silently — queries return rows, they are
just all `NULL`.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Engine | SQLite, WAL mode | DuckDB holds an exclusive file lock while writing, so a notebook could not query during a run. WAL allows concurrent readers alongside the single writer. `sqlite3` is in the standard library, so no new dependency. |
| Factor outcomes | Frozen snapshot at run end | The backend has a factor delete endpoint and auto-cleanup prunes caches, so library JSONs are mutable. Referencing them would let evidence vanish. |
| Usage granularity | One row per LLM call, with phase | ~40 rows per run. Per-model and per-run totals are then a `GROUP BY`, while stage-level cost analysis stays possible. Aggregating first would discard that irreversibly. |
| Cost totals | Derived, not stored | A stored total can drift from its detail rows. A view cannot. |
| Run kinds | One `run` table with a `kind` column | Mining and backtest share almost every column; separate tables would duplicate the schema and every query. |
| History | Backfill what is recoverable | Cost and model data for past runs was never written to disk and is unrecoverable. |

## Schema

Location: `data/runs.sqlite3`.

```sql
CREATE TABLE run (
  run_id         INTEGER PRIMARY KEY,
  experiment_id  TEXT UNIQUE,          -- exp_YYYYMMDD_HHMMSS; joins to logs, caches, factors
  task_id        TEXT,                 -- backend's 8-char id; only meaningful while the process lives
  kind           TEXT NOT NULL,        -- 'mining' | 'backtest'
  source         TEXT NOT NULL,        -- 'live' | 'backfill'
  status         TEXT NOT NULL,        -- 'running'|'completed'|'failed'|'cancelled'|'interrupted'

  llm_channel    TEXT,                 -- 'claude_cli'|'codex_cli'|'openai_api'
  llm_transport  TEXT,                 -- 'cli'|'api'
  llm_model      TEXT,                 -- configured model, e.g. 'opus'
  llm_endpoint   TEXT,                 -- API host; NULL for CLI channels

  direction      TEXT,
  market_mode    TEXT,
  market         TEXT,
  library_suffix TEXT,
  max_rounds     INTEGER,
  num_directions INTEGER,
  config_json    TEXT,                 -- full verbatim config snapshot

  started_at     TEXT NOT NULL,        -- ISO 8601
  finished_at    TEXT,
  duration_s     REAL,
  rounds_done    INTEGER,
  error          TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE llm_call (
  call_id           INTEGER PRIMARY KEY,
  run_id            INTEGER NOT NULL REFERENCES run(run_id) ON DELETE CASCADE,
  seq               INTEGER NOT NULL,  -- order within the run
  occurred_at       TEXT NOT NULL,
  phase             TEXT,              -- 'parsing'|'planning'|'evolving'|'backtesting'|'analyzing'
  round_number      INTEGER,
  model             TEXT,              -- model that actually served the call
  source            TEXT,              -- 'claude_cli'|'codex_cli'|'openai'
  transport         TEXT,              -- 'cli'|'api'|'other'
  prompt_tokens     INTEGER NOT NULL,
  completion_tokens INTEGER NOT NULL,
  cost_usd          REAL,              -- NULL means the provider reported none; distinct from 0
  UNIQUE (run_id, seq)
);

CREATE TABLE run_factor (
  run_factor_id   INTEGER PRIMARY KEY,
  run_id          INTEGER REFERENCES run(run_id) ON DELETE CASCADE,  -- NULL when unattributable
  factor_id       TEXT NOT NULL,
  factor_name     TEXT,
  expression      TEXT,
  library_file    TEXT,
  round_number    INTEGER,
  evolution_phase TEXT,                -- 'original'|'mutation'|'crossover'
  trajectory_id   TEXT,
  quality         TEXT,                -- 'high'|'medium'|'low'
  quality_score   REAL,

  ic REAL, icir REAL, rank_ic REAL, rank_icir REAL,
  ann_return REAL, sharpe REAL, max_drawdown REAL,
  portfolio_leg    TEXT,               -- 'long' | 'long_short'
  evaluation_split TEXT,               -- 'train' | 'valid' | 'test'

  metrics_json    TEXT,                -- full backtest_results verbatim
  captured_at     TEXT NOT NULL,
  UNIQUE (run_id, factor_id)
);

CREATE TABLE schema_meta (
  version    INTEGER NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE INDEX idx_llm_call_run   ON llm_call (run_id);
CREATE INDEX idx_llm_call_model ON llm_call (model);
CREATE INDEX idx_run_factor_run ON run_factor (run_id);
CREATE INDEX idx_run_started    ON run (started_at);

-- Required for backfill idempotency. SQLite treats NULLs as distinct in a
-- UNIQUE constraint, so UNIQUE (run_id, factor_id) does NOT stop a second
-- backfill from re-inserting every unattributed factor. Verified against
-- SQLite 3.47.1: without this index the duplicate insert is accepted.
CREATE UNIQUE INDEX idx_run_factor_unattributed
  ON run_factor (factor_id, library_file) WHERE run_id IS NULL;
```

Verified on the project's interpreter (`.venv`, SQLite 3.47.1): WAL mode engages, the
`FILTER` clause used by `run_cost` is supported, and the partial unique index above
rejects the duplicate that the table-level constraint lets through.

### Two columns that carry unusual weight

**`evaluation_split`.** This project enforces strict train/validation/test isolation and
locks the test set while mining runs (`app.py`, `get_factor_split_evaluation`). A factor
metric with no split recorded is not merely incomplete — it can be silently averaged
together with in-sample numbers, producing a result that looks fine and is wrong. Every
snapshotted metric records the split it came from.

**`portfolio_leg`.** An annualised return means something different for a long-only book
than for long–short. Averaging across factors without this column compares incomparable
quantities.

### View

```sql
CREATE VIEW run_cost AS
SELECT r.run_id,
       r.experiment_id,
       r.llm_model,
       r.llm_transport,
       count(c.call_id)                             AS calls,
       sum(c.prompt_tokens + c.completion_tokens)   AS total_tokens,
       sum(c.cost_usd)                              AS cost_usd,
       count(*) FILTER (WHERE c.cost_usd IS NULL)   AS uncosted_calls
FROM run r
LEFT JOIN llm_call c USING (run_id)
GROUP BY r.run_id;
```

`uncosted_calls` distinguishes a genuinely cheap run from one that was only partly
measured. Without it, `sum(cost_usd)` silently skips NULLs and a half-measured run reads
as a bargain.

## Write path

A new module `frontend-v2/backend/run_store.py`, single-purpose and independently
testable:

```
RunStore.open(path)                        connect, apply migrations, set pragmas
  .start_run(task) -> run_id               called from start_mining
  .record_call(run_id, record, phase, round)  called from _record_llm_usage
  .finish_run(run_id, status, …)           called from _mark_task_finished
  .snapshot_factors(run_id, experiment_id) reads the library, freezes rows
  .mark_interrupted()                      called once on backend startup
```

Pragmas: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`.

Three properties are deliberate:

1. **Writes are incremental, not deferred to the end.** A run killed mid-flight still
   leaves its cost record. Given that in-flight state has already been lost twice,
   writing only on completion would reproduce the failure this work exists to fix.
2. **`mark_interrupted()` runs at startup**, flipping any row left `running` to
   `interrupted`. Those subprocesses died with the previous backend; leaving them
   `running` forever would make the table lie.
3. **Accounting never breaks a run.** Every call is wrapped so a database error is logged
   and execution continues, following the principle already established in
   `_report_token_usage`: usage accounting must never take down a completion.

### Call sites in `app.py`

| Site | Action |
|---|---|
| `start_mining` / `start_backtest` | `start_run()` after the task dict is built |
| `_run_mining`, after `_describe_llm_channel` | update the run row with channel, model, transport, endpoint |
| `_record_llm_usage` | `record_call()` with the current phase and round |
| `_mark_task_finished` | `finish_run()` then `snapshot_factors()` |
| application startup | `mark_interrupted()` |

## Backfill

`tools/backfill_runs.py`, idempotent and safe to re-run:

- Scan `log/exp_*` directories. Insert a `run` row per directory with `source='backfill'`,
  `experiment_id` and `started_at` parsed from the directory name, `status='completed'`.
- Scan `data/factorlib/all_factors_library_*.json`. Insert a `run_factor` row per factor,
  attaching it to its run when `metadata.experiment_id` is a real id, otherwise leaving
  `run_id` NULL.
- Leave `llm_channel`, `llm_model` and all `llm_call` rows absent. That data was never
  written to disk and cannot be recovered.

Expected result: one run row per `log/exp_*` directory (18 at the time of writing), with
only those factors whose `metadata.experiment_id` is a real id attached to a run. Every
other factor lands with `run_id` NULL. Because the libraries keep growing, the backfill
script reports its own tallies rather than asserting fixed counts, and the test asserts
idempotency rather than a specific row count.

Analysis that concerns cost must filter `WHERE source = 'live'`. The `source` column
exists precisely so that a NULL cost is never mistaken for a free run.

## Testing

`tests/test_run_store.py`, matching the pytest convention of the four existing test files.
Each test runs against a temporary database file.

- Migrations apply cleanly on an empty file, and applying them twice is a no-op.
- A cancelled run retains the calls recorded before cancellation.
- `cost_usd` NULL stays NULL through the `run_cost` view and never becomes `0`.
- `uncosted_calls` counts correctly when a run mixes costed and uncosted calls.
- `mark_interrupted()` changes only `running` rows and leaves terminal rows untouched.
- `record_call` is rejected for a `run_id` that does not exist, rather than silently
  inserting an orphan.
- Running the backfill twice produces no duplicate rows, including for factors with
  `run_id` NULL — the case the table-level UNIQUE constraint does not cover.
- A database error inside `record_call` is swallowed and does not propagate.

## Out of scope

- Prompt and completion text. It is large (7k–11k characters per prompt) and already
  present in `log/exp_*`.
- A dashboard UI for run history. The database is the deliverable; surfacing it is
  separate work.
- Migrating the in-memory `tasks` dict to read from the database. The dict stays the
  live source for the running UI; the database is the durable record beside it.
- Retention and pruning. At roughly 40 call rows per run, volume is not a concern until
  there are thousands of runs. Note `log/` is already 2.6 GB; pruning that is a separate
  concern from this database, which stores only metadata.

## Risks

| Risk | Mitigation |
|---|---|
| The `experiment_id` fix is skipped or regresses, leaving factors unattributable | Make it the first implementation task; add a test asserting a real id is written when `EXPERIMENT_ID` is set |
| Snapshot drifts from the library after a factor is re-evaluated | Accepted. `captured_at` records when the snapshot was taken; re-evaluation history was considered and rejected as too heavy |
| Concurrent writes from a future parallel pipeline | Single-writer today, since the backend is one asyncio process. `busy_timeout` covers brief contention; revisit if the pipeline ever writes directly |
| Backfilled rows with NULL cost treated as free runs | The `source` column plus `uncosted_calls` in the view; documented in the query recipes |

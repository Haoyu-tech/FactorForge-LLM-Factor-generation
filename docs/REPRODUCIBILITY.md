# Reproduction guide

## Fresh-clone prerequisites

The existing [Quickstart](../README.md#quickstart) assumes a local `llm-factor` Conda environment. That command activates an existing environment; it does not create or specify one.

[adapter/sp500_loader.py](../adapter/sp500_loader.py) expects parser/operator source under `QuantaAlpha/quantaalpha/factors/coder/`. The `QuantaAlpha/` folder is absent from this checkout. Supply the compatible upstream source and record its exact commit before evaluation; a guessed latest revision is not a reference environment.

WRDS/CRSP/Compustat source files and generated monthly panels are external. Review [configs/](../configs/) and [llm_factor/config.py](../llm_factor/config.py) for configured paths.

## Execution route

After restoring dependencies and input data, follow the README panel-build sequence, then evaluate a known expression:

```powershell
python adapter/evaluate_ic.py '$ret_12_1'
```

Keep single quotes around dollar-prefixed expressions in PowerShell. This command is a reproduction target; it was not executed during cleanup.

## Offline evaluation and live generation

Evaluating stored formulas and inspecting committed reports is separate from generating new candidates with an LLM. Live generation additionally needs the configured provider credentials. Do not commit credentials or include them in an environment export.

For comparable results, retain the upstream commit, panel fingerprint, candidate ledger, discovery budget, train/test split, prompts, model configuration and software versions. A versioned environment specification remains to be added.

## Run record

For every result you intend to compare or share, retain the repository commit, exact command/configuration, input-data identity, environment versions and output location. Save a dependency snapshot after a successful reference run; newly added requirements lists are intentionally unpinned until that validation exists.

## Validation status

Cleanup review: 14 October 2026. File paths and documented entry points were checked against the checkout. Full empirical results were not regenerated. Project-specific external prerequisites and known blockers are listed above.

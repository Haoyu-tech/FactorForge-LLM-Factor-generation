import hashlib
import json
import os
import time
from pathlib import Path

from quantaalpha.utils.cache_cleanup import cleanup_mining_artifacts


def test_cleanup_keeps_referenced_factor_and_datasets(tmp_path):
    project = tmp_path / "project"
    factorlib = project / "data/factorlib"
    cache = project / "data/results/factor_cache"
    workspace = project / "data/results/workspace_exp_done"
    qlib = project / "data/qlib/wrds_sp500"
    log_cache = project / "log/2026-01-01/pickle_cache_0"
    for path in (factorlib, cache, workspace, qlib, log_cache):
        path.mkdir(parents=True, exist_ok=True)
    expression = "RANK($close)"
    keep = hashlib.md5(expression.encode()).hexdigest()
    orphan = "f" * 32
    (cache / f"{keep}.pkl").write_bytes(b"keep")
    (cache / f"{orphan}.pkl").write_bytes(b"remove")
    (workspace / "large.tmp").write_bytes(b"workspace")
    (qlib / "day.bin").write_bytes(b"dataset")
    (log_cache / "cache.pkl").write_bytes(b"log")
    factorlib.joinpath("all_factors_library_x.json").write_text(json.dumps({
        "factors": {"1": {"factor_expression": expression}}
    }), encoding="utf-8")
    old = time.time() - 48 * 3600
    os.utime(cache / f"{orphan}.pkl", (old, old))
    os.utime(log_cache, (old, old))
    result = cleanup_mining_artifacts(
        project, finished_workspace=workspace,
        stale_hours=1, log_cache_hours=1,
        orphan_factor_cache_hours=1,
    )
    assert not workspace.exists()
    assert not log_cache.exists()
    assert not (cache / f"{orphan}.pkl").exists()
    assert (cache / f"{keep}.pkl").exists()
    assert (qlib / "day.bin").exists()
    assert result["bytes_freed"] > 0

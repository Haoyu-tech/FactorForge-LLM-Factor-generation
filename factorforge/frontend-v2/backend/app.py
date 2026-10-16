"""
QuantaAlpha Backend API
FastAPI-based REST + WebSocket API for factor mining and backtesting.

Integrates with the core QuantaAlpha CLI to launch experiments
and reads factor library JSON for the factor browsing API.
"""

import asyncio
import glob
import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Resolve project root (two levels up from this file: frontend-v2/backend/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Ensure import quantaalpha is available (when backend is started from frontend-v2 directory, repo root is not in sys.path)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DOTENV_PATH = PROJECT_ROOT / ".env"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="QuantaAlpha API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================== Pydantic Models ==========================


class MiningStartRequest(BaseModel):
    """Request to start a factor mining experiment."""
    direction: str = Field(..., description="Research direction, e.g. '价量因子挖掘'")
    numDirections: Optional[int] = Field(2, ge=1, le=10, description="Exploration directions")
    maxRounds: Optional[int] = Field(3, ge=1, le=20, description="Evolution rounds")
    maxLoops: Optional[int] = Field(2, ge=1, le=20, description="Iterations per direction")
    factorsPerHypothesis: Optional[int] = Field(3, ge=1, le=10, description="Factors per hypothesis")
    librarySuffix: Optional[str] = Field(None, description="Factor library file suffix")
    qualityGateEnabled: Optional[bool] = Field(None, description="Enable quality gate checks")
    miningLightgbmEnabled: bool = Field(False, description="Train a LightGBM combination during factor mining")
    parallelEnabled: Optional[bool] = Field(None, description="Enable parallel execution within evolution phases")
    evaluationFrequencies: List[str] = Field(
        default_factory=lambda: ["day"],
        description="Portfolio rebalance frequencies: day | week | month",
    )
    dataSource: str = Field("wrds", pattern="^(qlib|wrds|cn_duckdb|binance_futures)$")
    marketMode: str = Field("us", pattern="^(us|cn|crypto)$")
    market: str = Field("sp500", pattern="^(sp500|csi300|csi500|sme_composite|binance_usdm)$")
    excludeSt: bool = Field(True, description="Exclude ST stocks on each observation date")
    excludeNewStocks: bool = Field(True, description="Exclude newly listed stocks")
    excludeChiNext: bool = Field(False, description="Exclude ChiNext stocks")
    excludeStar: bool = Field(False, description="Exclude STAR Market stocks")
    excludeBse: bool = Field(False, description="Exclude Beijing Stock Exchange stocks")
    newStockMinTradingDays: int = Field(375, ge=0, le=2000)
    trainStartDate: str = Field("1925-12-31")
    trainEndDate: str = Field("1999-12-31")
    validStartDate: str = Field("2000-01-03")
    validEndDate: str = Field("2009-12-31")
    testStartDate: str = Field("2010-01-04")
    testEndDate: str = Field("2025-12-31")


class FactorDeleteRequest(BaseModel):
    factorIds: List[str] = Field(..., min_length=1, description="Factor IDs to delete")
    library: Optional[str] = Field(None, description="Factor library JSON filename")
    marketMode: Optional[str] = Field(None, pattern="^(us|cn|crypto)$")
    market: Optional[str] = Field(None, pattern="^(sp500|csi300|csi500|sme_composite|binance_usdm)$")


class FactorCorrelationRequest(BaseModel):
    factorIds: List[str] = Field(..., min_length=2, max_length=40)
    library: Optional[str] = Field(None, description="Factor library JSON filename or __all__")
    method: str = Field("spearman", pattern="^(spearman|pearson)$")
    startDate: Optional[str] = None
    endDate: Optional[str] = None


class WrdsBuildRequest(BaseModel):
    startDate: str = Field("1925-12-31")
    endDate: str = Field("2025-12-31")


class ChinaBuildRequest(BaseModel):
    startDate: str = Field("2010-01-04")
    endDate: str = Field("2025-12-31")


class CryptoBuildRequest(BaseModel):
    startDate: str = Field("2020-01-01")
    endDate: str = Field("2025-12-31")
    maxSymbols: int = Field(100, ge=10, le=300)


class BacktestStartRequest(BaseModel):
    """Request to start an independent backtest."""
    factorJson: str = Field("", description="Path to factor library JSON")
    factorSource: str = Field("custom", pattern="^(custom|combined|kelly_jkp)$",
                              description="custom | combined | kelly_jkp")
    configPath: Optional[str] = Field(None, description="Path to backtest config")
    portfolioMode: str = Field("long", pattern="^(long|short|long_short)$",
                               description="long | short | long_short")
    qualityFilter: str = Field("all", pattern="^(all|high|medium|low)$",
                               description="all | high | medium | low")
    kellyMissingThreshold: float = Field(0.20, ge=0.0, le=1.0)
    model: Optional[str] = Field(None, pattern="^(lightgbm|pls5|lasso)$")
    kellyModel: str = Field("lightgbm", pattern="^(lightgbm|pls5|lasso)$")
    kellyRetrainMonths: int = Field(12, ge=1, le=60)
    kellyMinTrainYears: int = Field(10, ge=3, le=50)
    retrainMonths: Optional[int] = Field(None, ge=1, le=60)
    minTrainYears: Optional[int] = Field(None, ge=3, le=50)
    portfolioOptimization: bool = False
    correlationPruning: bool = False
    correlationThreshold: float = Field(0.85, ge=0.5, lt=1.0)


class SystemConfigUpdate(BaseModel):
    """Partial update to system configuration (.env)."""
    QLIB_DATA_DIR: Optional[str] = None
    DATA_RESULTS_DIR: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    CHAT_MODEL: Optional[str] = None
    REASONING_MODEL: Optional[str] = None
    USE_CODEX_CLI: Optional[bool] = None
    CODEX_CLI_MODEL: Optional[str] = None
    USE_CLAUDE_CLI: Optional[bool] = None
    CLAUDE_CLI_MODEL: Optional[str] = None
    CLAUDE_CLI_COMMAND: Optional[str] = None
    CLAUDE_CLI_TIMEOUT_SECONDS: Optional[int] = None
    CODEX_CLI_COMMAND: Optional[str] = None
    CODEX_CLI_TIMEOUT_SECONDS: Optional[int] = None
    MINING_EVALUATION_FREQUENCIES: Optional[str] = None
    MINING_LIGHTGBM_ENABLED: Optional[bool] = None
    DATA_SOURCE: Optional[str] = None
    WRDS_ROOT: Optional[str] = None
    WRDS_QLIB_DATA_DIR: Optional[str] = None
    MARKET_MODE: Optional[str] = None
    DEFAULT_MARKET: Optional[str] = None
    CN_DUCKDB_PATH: Optional[str] = None
    CN_QLIB_DATA_DIR: Optional[str] = None
    CN_EXCLUDE_ST: Optional[bool] = None
    CN_EXCLUDE_NEW_STOCKS: Optional[bool] = None
    CN_EXCLUDE_CHINEXT: Optional[bool] = None
    CN_EXCLUDE_STAR: Optional[bool] = None
    CN_EXCLUDE_BSE: Optional[bool] = None
    CN_NEW_STOCK_MIN_TRADING_DAYS: Optional[int] = Field(None, ge=0, le=2000)
    CRYPTO_QLIB_DATA_DIR: Optional[str] = None
    CRYPTO_MAX_SYMBOLS: Optional[int] = Field(None, ge=10, le=300)
    CRYPTO_MIN_LISTING_DAYS: Optional[int] = Field(None, ge=0, le=3650)
    TRAIN_START_DATE: Optional[str] = None
    TRAIN_END_DATE: Optional[str] = None
    VALID_START_DATE: Optional[str] = None
    VALID_END_DATE: Optional[str] = None
    TEST_START_DATE: Optional[str] = None
    TEST_END_DATE: Optional[str] = None
    US_TRAIN_START_DATE: Optional[str] = None
    US_TRAIN_END_DATE: Optional[str] = None
    US_VALID_START_DATE: Optional[str] = None
    US_VALID_END_DATE: Optional[str] = None
    US_TEST_START_DATE: Optional[str] = None
    US_TEST_END_DATE: Optional[str] = None
    CN_TRAIN_START_DATE: Optional[str] = None
    CN_TRAIN_END_DATE: Optional[str] = None
    CN_VALID_START_DATE: Optional[str] = None
    CN_VALID_END_DATE: Optional[str] = None
    CN_TEST_START_DATE: Optional[str] = None
    CN_TEST_END_DATE: Optional[str] = None
    AUTO_CLEANUP_ENABLED: Optional[bool] = None
    CACHE_RETENTION_HOURS: Optional[int] = Field(None, ge=1, le=720)
    LOG_CACHE_RETENTION_HOURS: Optional[int] = Field(None, ge=1, le=720)
    ORPHAN_FACTOR_CACHE_RETENTION_HOURS: Optional[int] = Field(None, ge=1, le=2160)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None


# ========================== In-Memory State ==========================

tasks: Dict[str, Dict[str, Any]] = {}
ws_connections: Dict[str, List[WebSocket]] = {}  # task_id -> list of WS


# ========================== Utility Helpers ==========================

def _gen_id() -> str:
    return str(uuid.uuid4())[:8]


def _now() -> str:
    return datetime.now().isoformat()


def _total_memory_gib() -> float:
    """Return the memory visible to this WSL instance."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return float(pages * page_size) / (1024 ** 3)
    except (AttributeError, OSError, ValueError):
        return 0.0


def _load_dotenv_dict() -> Dict[str, str]:
    """Parse the .env file into a dict, including dotenv-style quoted values."""
    env: Dict[str, str] = {}
    if DOTENV_PATH.exists():
        for line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key, _, val = stripped.partition("=")
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
                    val = val[1:-1]
                env[key.strip()] = val
    return env


def _find_factor_jsons() -> List[str]:
    """Find all factor library JSON files in data/factorlib/."""
    factorlib_dir = PROJECT_ROOT / "data" / "factorlib"
    pattern = str(factorlib_dir / "all_factors_library*.json")
    results = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

    old_pattern = str(PROJECT_ROOT / "all_factors_library*.json")
    old_results = sorted(glob.glob(old_pattern), key=os.path.getmtime, reverse=True)

    seen = set(results)
    for r in old_results:
        if r not in seen:
            results.append(r)
    return results


def _factor_library_scope(path: str | Path, raw: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Return the market ownership of a library; legacy files are US/S&P 500."""
    metadata = (raw or {}).get("metadata", {}) if isinstance(raw, dict) else {}
    market_mode = str(metadata.get("market_mode") or "").lower()
    market = str(metadata.get("market") or "").lower()
    filename = Path(path).name.lower()
    if not market_mode:
        if "all_factors_library_crypto_" in filename:
            market_mode = "crypto"
        else:
            market_mode = "cn" if "all_factors_library_cn_" in filename else "us"
    if not market:
        if market_mode == "crypto":
            market = "binance_usdm"
        elif market_mode == "cn":
            market = next(
                (value for value in ("csi300", "csi500", "sme_composite")
                 if f"all_factors_library_cn_{value}" in filename),
                "csi300",
            )
        else:
            market = "sp500"
    labels = {
        "sp500": "S&P 500",
        "csi300": "沪深300",
        "csi500": "中证500",
        "sme_composite": "中小综指",
        "binance_usdm": "Binance USDT 永续",
    }
    return {"marketMode": market_mode, "market": market, "label": labels.get(market, market)}


def _build_total_factor_library(
    market_mode: str,
    market: str,
    output_path: Path,
) -> Dict[str, Any]:
    """Merge all historical snapshots for one market; newest duplicate wins."""
    merged: Dict[str, Any] = {}
    identities: set[tuple[str, str]] = set()
    sources: List[str] = []
    for raw_path in _find_factor_jsons():
        path = Path(raw_path)
        try:
            payload = _load_factor_library(str(path))
        except Exception:
            continue
        scope = _factor_library_scope(path, payload)
        if scope["marketMode"] != market_mode or scope["market"] != market:
            continue
        sources.append(path.name)
        for key, info in (payload.get("factors") or {}).items():
            if not isinstance(info, dict):
                continue
            expression = str(info.get("factor_expression") or "").strip()
            factor_id = str(info.get("factor_id") or key).strip()
            identity = ("expression", expression) if expression else ("id", factor_id)
            if identity in identities:
                continue
            identities.add(identity)
            output_id = factor_id or hashlib.md5(expression.encode()).hexdigest()[:16]
            if output_id in merged:
                output_id = hashlib.md5(f"{output_id}:{expression}".encode()).hexdigest()[:16]
            record = dict(info)
            for bulky_key in (
                "split_results", "decile_curves", "llm_explanation", "feedback",
            ):
                record.pop(bulky_key, None)
            record["factor_id"] = output_id
            record["market_mode"] = market_mode
            record["market"] = market
            record["source_library"] = path.name
            merged[output_id] = record
    if not merged:
        raise FileNotFoundError(f"No factors found for {market_mode}/{market}")
    dotenv = _load_dotenv_dict()
    prefix = "CRYPTO" if market_mode == "crypto" else ("CN" if market_mode == "cn" else "US")
    windows = {}
    for split, stem in (("train", "TRAIN"), ("valid", "VALID"), ("test", "TEST")):
        start = dotenv.get(f"{prefix}_{stem}_START_DATE") or dotenv.get(f"{stem}_START_DATE")
        end = dotenv.get(f"{prefix}_{stem}_END_DATE") or dotenv.get(f"{stem}_END_DATE")
        if start and end:
            windows[split] = [start, end]
    aggregate = {
        "metadata": {
            "market_mode": market_mode,
            "market": market,
            "total_factors": len(merged),
            "all_history": True,
            "merged_deduplicated": True,
            "source_libraries": sources,
            "split_windows": windows,
            "created_at": _now(),
        },
        "factors": merged,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    temp.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp, output_path)
    return aggregate


def _factor_split_windows(
    factor_info: Dict[str, Any],
    library_metadata: Dict[str, Any],
    market_mode: str,
) -> Dict[str, List[str]]:
    """Resolve immutable library windows, falling back to market-specific config."""
    factor_metadata = factor_info.get("metadata") or {}
    windows = factor_metadata.get("split_windows") or library_metadata.get("split_windows")
    if isinstance(windows, dict) and windows:
        return windows
    dotenv = _load_dotenv_dict()
    prefix = "CRYPTO" if market_mode == "crypto" else ("CN" if market_mode == "cn" else "US")
    output: Dict[str, List[str]] = {}
    for split, stem in (("train", "TRAIN"), ("valid", "VALID"), ("test", "TEST")):
        start = dotenv.get(f"{prefix}_{stem}_START_DATE") or dotenv.get(f"{stem}_START_DATE")
        end = dotenv.get(f"{prefix}_{stem}_END_DATE") or dotenv.get(f"{stem}_END_DATE")
        if start and end:
            output[split] = [start, end]
    return output


def _valid_factor_split_results(
    factor_info: Dict[str, Any],
    library_metadata: Dict[str, Any],
    market_mode: str,
) -> Dict[str, Any]:
    """Hide stale cross-market caches whose dates do not match this library."""
    expected = _factor_split_windows(factor_info, library_metadata, market_mode)
    benchmark_records = library_metadata.get("benchmark_curves", {}) \
        if isinstance(library_metadata, dict) else {}
    valid: Dict[str, Any] = {}
    for split, result in (factor_info.get("split_results") or {}).items():
        window = expected.get(split)
        if not isinstance(result, dict):
            continue
        if window and [str(result.get("startDate")), str(result.get("endDate"))] != [str(window[0]), str(window[1])]:
            continue
        output = dict(result)
        benchmark = benchmark_records.get(split) if isinstance(benchmark_records, dict) else None
        if (
            market_mode == "us"
            and isinstance(benchmark, dict)
            and (not window or [str(benchmark.get("startDate")), str(benchmark.get("endDate"))]
                 == [str(window[0]), str(window[1])])
        ):
            output["benchmarkCurve"] = benchmark.get("curve") or []
            output["benchmarkLabel"] = benchmark.get("label") or "S&P 500"
        valid[split] = output
    return valid


def _prune_stale_factor_split_caches() -> Dict[str, Any]:
    """Remove persisted split results that belong to another market window."""
    removed = 0
    changed_libraries: List[str] = []
    for raw_path in _find_factor_jsons():
        path = Path(raw_path)
        try:
            payload = _load_factor_library(str(path))
            scope = _factor_library_scope(path, payload)
            metadata = payload.get("metadata", {})
            changed = False
            for factor in (payload.get("factors") or {}).values():
                if not isinstance(factor, dict):
                    continue
                stored = factor.get("split_results")
                if not isinstance(stored, dict) or not stored:
                    continue
                valid = _valid_factor_split_results(
                    factor, metadata, scope["marketMode"]
                )
                removed += len(stored) - len(valid)
                if len(valid) != len(stored):
                    factor["split_results"] = valid
                    changed = True
            if changed:
                temp = path.with_suffix(path.suffix + f".prune.{os.getpid()}.tmp")
                temp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                os.replace(temp, path)
                changed_libraries.append(path.name)
        except Exception:
            continue
    return {"removed": removed, "changedLibraries": changed_libraries}


@app.on_event("startup")
async def prune_stale_factor_split_caches_on_startup() -> None:
    result = await asyncio.to_thread(_prune_stale_factor_split_caches)
    if result["removed"]:
        print(
            f"Pruned {result['removed']} stale split caches from "
            f"{len(result['changedLibraries'])} factor libraries",
            flush=True,
        )


def _load_factor_library(path: str) -> Dict[str, Any]:
    """Load a factor library, tolerating a complete document plus a torn tail."""
    from quantaalpha.factors.library import _decode_library_text
    return _decode_library_text(Path(path).read_text(encoding="utf-8"))


def _assess_quality(factor_info: Dict[str, Any]) -> Dict[str, Any]:
    """Use the shared multi-dimensional quality assessment."""
    from quantaalpha.backtest.factor_loader import assess_factor_quality
    return assess_factor_quality(factor_info)


def _classify_quality(factor_info: Dict[str, Any]) -> str:
    return _assess_quality(factor_info)["quality"]


def _metric_number(value: Any) -> Optional[float]:
    """Return a finite numeric metric while preserving valid zero values."""
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _factor_frequency(bt: Dict[str, Any], preferred: Optional[List[str]] = None) -> Optional[str]:
    """Select the evaluated rebalance frequency actually present in a factor result."""
    candidates = list(preferred or []) + ["day", "week", "month"]
    seen = set()
    for frequency in candidates:
        if not frequency or frequency in seen:
            continue
        seen.add(frequency)
        prefix = f"{frequency}.long_short."
        if any(str(key).startswith(prefix) for key in bt):
            return frequency
    return None


def _portfolio_statistics(bt: Dict[str, Any], frequency: Optional[str]) -> Dict[str, Any]:
    if not frequency:
        return {}
    result: Dict[str, Any] = {}
    field_map = {
        "annualizedGrossReturn": "annualized_gross_return",
        "annualizedNetReturn": "annualized_net_return",
        "sharpeRatio": "sharpe_ratio",
        "maxDrawdown": "max_drawdown",
        "turnover": "annualized_turnover",
        "transactionCost": "total_transaction_cost",
        "borrowCost": "total_borrow_cost",
    }
    for leg in ("long", "short", "long_short"):
        leg_result: Dict[str, Optional[float]] = {}
        for output_name, metric_name in field_map.items():
            leg_result[output_name] = _metric_number(bt.get(f"{frequency}.{leg}.{metric_name}"))
        result[leg] = leg_result
    result["decileMonotonicity"] = _metric_number(bt.get(f"{frequency}.decile_monotonicity"))
    return result


def _asset_pricing_statistics(bt: Dict[str, Any], frequency: Optional[str]) -> Dict[str, Any]:
    """Expose FF3/FF5 regressions, with and without momentum, including beta tests."""
    if not frequency:
        return {}
    output: Dict[str, Any] = {}
    for model in ("ff3", "ff3_mom", "ff5", "ff5_mom"):
        prefix = f"{frequency}.asset_pricing.{model}."
        raw = {str(key)[len(prefix):]: value for key, value in bt.items() if str(key).startswith(prefix)}
        if not raw:
            continue
        betas: Dict[str, Any] = {}
        for name, value in raw.items():
            if not name.startswith("beta_") or name.endswith(("_t_stat", "_p_value")):
                continue
            factor_name = name[5:].upper()
            betas[factor_name] = {
                "value": _metric_number(value),
                "tStat": _metric_number(raw.get(f"{name}_t_stat")),
                "pValue": _metric_number(raw.get(f"{name}_p_value")),
            }
        output[model] = {
            "alphaAnnualized": _metric_number(raw.get("alpha_annualized")),
            "alphaTStat": _metric_number(raw.get("alpha_t_stat")),
            "alphaPValue": _metric_number(raw.get("alpha_p_value")),
            "rSquared": _metric_number(raw.get("r_squared")),
            "adjustedRSquared": _metric_number(raw.get("adjusted_r_squared")),
            "observations": _metric_number(raw.get("observations")),
            "betas": betas,
        }
    return output


def _industry_statistics(bt: Dict[str, Any], frequency: Optional[str]) -> Dict[str, Any]:
    """Collect GICS coverage/exposure and ggroup robustness metrics for the UI."""
    levels: Dict[str, Any] = {}
    for level in ("gsector", "ggroup", "gind", "gsubind"):
        prefix = f"industry.{level}."
        levels[level] = {
            "coverage": _metric_number(bt.get(prefix + "coverage")),
            "meanAbsExposure": _metric_number(bt.get(prefix + "mean_abs_exposure")),
            "maxAbsExposure": _metric_number(bt.get(prefix + "max_abs_exposure")),
            "exposureHhi": _metric_number(bt.get(prefix + "exposure_hhi")),
            "groupCount": _metric_number(bt.get(prefix + "group_count")),
        }
    robustness: Dict[str, Any] = {
        "ic": _metric_number(bt.get("industry.ggroup.robustness.IC")),
        "icir": _metric_number(bt.get("industry.ggroup.robustness.ICIR")),
        "rankIc": _metric_number(bt.get("industry.ggroup.robustness.Rank IC")),
        "rankIcir": _metric_number(bt.get("industry.ggroup.robustness.Rank ICIR")),
    }
    if frequency:
        prefix = f"industry.ggroup.robustness.{frequency}.long_short."
        robustness.update({
            "annualizedNetReturn": _metric_number(bt.get(prefix + "annualized_net_return")),
            "sharpeRatio": _metric_number(bt.get(prefix + "sharpe_ratio")),
            "maxDrawdown": _metric_number(bt.get(prefix + "max_drawdown")),
            "decileMonotonicity": _metric_number(
                bt.get(f"industry.ggroup.robustness.{frequency}.decile_monotonicity")
            ),
        })
    return {
        "primaryLevel": "gsector",
        "robustnessLevel": "ggroup",
        "levels": levels,
        "ggroupRobustness": robustness,
    }


async def _broadcast(task_id: str, message: Dict[str, Any]):
    """Send a JSON message to all WebSocket clients for a task."""
    if task_id not in ws_connections:
        return
    dead: List[WebSocket] = []
    for ws in ws_connections[task_id]:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_connections[task_id].remove(ws)


# ========================== Mining Process ==========================

async def _run_mining(task_id: str, req: MiningStartRequest):
    """
    Launch the actual QuantaAlpha mining experiment as a subprocess
    and stream its output over WebSocket.
    """
    task = tasks[task_id]
    cleanup_paths = {}
    try:
        # Build the command
        env = os.environ.copy()
        # Prevent each mining child from creating a full CPU-sized BLAS pool.
        # With several evolution workers that multiplies both thread count and
        # memory usage and can trigger the WSL OOM killer.
        env.update({
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
            "NUMEXPR_NUM_THREADS": "2",
            "VECLIB_MAXIMUM_THREADS": "2",
            "MALLOC_ARENA_MAX": "2",
        })
        # Load .env into env
        dotenv = _load_dotenv_dict()
        env.update(dotenv)
        # Qlib/RDAgent still uses MLflow's local FileStore. Newer MLflow
        # releases require an explicit compatibility opt-in.
        env.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

        # A backend launched by systemd does not necessarily inherit the
        # interactive Conda shell variables. RDAgent's LocalEnv requires
        # CONDA_DEFAULT_ENV to be a string, and its child commands need the
        # active environment's bin directory on PATH.
        conda_env_name = dotenv.get("CONDA_ENV_NAME", "quantaalpha")
        active_prefix = str(Path(sys.executable).resolve().parent.parent)
        env["CONDA_DEFAULT_ENV"] = conda_env_name
        env["CONDA_PREFIX"] = active_prefix
        env["PATH"] = os.pathsep.join(
            path for path in (
                str(Path(active_prefix) / "bin"),
                str(Path.home() / "miniconda3" / "condabin"),
                env.get("PATH", ""),
            )
            if path
        )
        if str(dotenv.get("USE_CLAUDE_CLI", "")).lower() in {"1", "true", "yes", "on"}:
            env["USE_CLAUDE_CLI"] = "true"
            env["USE_CODEX_CLI"] = "false"
            env["BACKEND"] = "quantaalpha.llm.rdagent_claude_backend.ClaudeCLIAPIBackend"
        elif str(dotenv.get("USE_CODEX_CLI", "")).lower() in {"1", "true", "yes", "on"}:
            env["USE_CODEX_CLI"] = "true"
            env["USE_CLAUDE_CLI"] = "false"
            env["BACKEND"] = "quantaalpha.llm.rdagent_codex_backend.CodexCLIAPIBackend"

        # Use experiment_id as suffix to guarantee isolation
        experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        env["EXPERIMENT_ID"] = experiment_id
        env["LOG_TRACE_PATH"] = str(PROJECT_ROOT / "log" / experiment_id)
        
        if req.marketMode == "crypto" or req.dataSource == "binance_futures":
            market_mode, market = "crypto", "binance_usdm"
        elif req.marketMode == "cn" or req.dataSource == "cn_duckdb":
            market_mode, market = "cn", req.market
        else:
            market_mode, market = "us", "sp500"
        # Enforce unique, market-scoped library names. A custom suffix remains
        # visible but is always prefixed with e.g. cn_csi300 or us_sp500.
        requested_suffix = req.librarySuffix or experiment_id
        scope_prefix = f"{market_mode}_{market}"
        if not requested_suffix.startswith(f"{scope_prefix}_"):
            requested_suffix = f"{scope_prefix}_{requested_suffix}"
        req.librarySuffix = requested_suffix
        task["config"]["librarySuffix"] = req.librarySuffix
        env["FACTOR_LIBRARY_SUFFIX"] = req.librarySuffix
        env["MINING_LIGHTGBM_ENABLED"] = "true" if req.miningLightgbmEnabled else "false"
        task["config"]["miningLightgbmEnabled"] = req.miningLightgbmEnabled

        date_overrides = {
            "TRAIN_START_DATE": req.trainStartDate,
            "TRAIN_END_DATE": req.trainEndDate,
            "VALID_START_DATE": req.validStartDate,
            "VALID_END_DATE": req.validEndDate,
            "TEST_START_DATE": req.testStartDate,
            "TEST_END_DATE": req.testEndDate,
        }
        env.update(date_overrides)
        env["DATA_SOURCE"] = (
            "binance_futures" if market_mode == "crypto"
            else ("cn_duckdb" if market_mode == "cn" else req.dataSource)
        )
        env["MARKET_MODE"] = market_mode
        env["QLIB_MARKET"] = market
        env["CN_EXCLUDE_ST"] = "true" if req.excludeSt else "false"
        env["CN_EXCLUDE_NEW_STOCKS"] = "true" if req.excludeNewStocks else "false"
        env["CN_EXCLUDE_CHINEXT"] = "true" if req.excludeChiNext else "false"
        env["CN_EXCLUDE_STAR"] = "true" if req.excludeStar else "false"
        env["CN_EXCLUDE_BSE"] = "true" if req.excludeBse else "false"
        env["CN_NEW_STOCK_MIN_TRADING_DAYS"] = str(req.newStockMinTradingDays)
        env["CRYPTO_MIN_LISTING_DAYS"] = str(dotenv.get("CRYPTO_MIN_LISTING_DAYS", "90"))
        task["config"].update({
            "marketMode": market_mode, "market": market,
            "excludeSt": req.excludeSt, "excludeNewStocks": req.excludeNewStocks,
            "excludeChiNext": req.excludeChiNext, "excludeStar": req.excludeStar,
            "excludeBse": req.excludeBse, "newStockMinTradingDays": req.newStockMinTradingDays,
        })
        # Mining learns from validation only. The held-out test segment is
        # evaluated by the independent backtest and never fed to the LLM.
        env["MINING_EVALUATION_SPLIT"] = "valid"
        if market_mode == "crypto":
            crypto_qlib = dotenv.get(
                "CRYPTO_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "binance_usdm")
            )
            if not Path(crypto_qlib).joinpath("calendars", "day.txt").exists():
                raise RuntimeError("币安 USDT 永续 Qlib 数据尚未构建。请先在系统配置的数据路径页构建。")
            if not Path(crypto_qlib).joinpath("instruments", "binance_usdm.txt").exists():
                raise RuntimeError("币安 USDT 永续合约池尚未构建：binance_usdm")
            env["QLIB_DATA_DIR"] = crypto_qlib
            # Qlib has no crypto region constant; REG_US supplies compatible
            # expression/calendar behavior while MARKET_MODE remains crypto.
            env["QLIB_REGION"] = "us"
        elif market_mode == "cn":
            cn_qlib = dotenv.get(
                "CN_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "cn_market")
            )
            if not Path(cn_qlib).joinpath("calendars", "day.txt").exists():
                raise RuntimeError("A股 Qlib 数据尚未构建。请先在系统配置的数据路径页检查并构建 market.db。")
            instrument_file = Path(cn_qlib) / "instruments" / f"{market}.txt"
            if not instrument_file.exists():
                raise RuntimeError(f"A股股票池尚未构建：{market}")
            env["QLIB_DATA_DIR"] = cn_qlib
            env["QLIB_REGION"] = "cn"
        elif req.dataSource == "wrds":
            wrds_qlib = dotenv.get(
                "WRDS_QLIB_DATA_DIR",
                str(PROJECT_ROOT / "data" / "qlib" / "wrds_sp500"),
            )
            if not Path(wrds_qlib).joinpath("calendars", "day.txt").exists():
                raise RuntimeError(
                    "WRDS Qlib data has not been built yet. Configure WRDS_ROOT and build the WRDS S&P 500 dataset first."
                )
            env["QLIB_DATA_DIR"] = wrds_qlib
            env["QLIB_REGION"] = "us"

        results_base = dotenv.get("DATA_RESULTS_DIR", str(PROJECT_ROOT / "data" / "results"))
        source_cache = Path(results_base) / f"factor_source_{env['DATA_SOURCE']}_{market}"
        env["FACTOR_COSTEER_DATA_FOLDER"] = str(source_cache / "all")
        env["FACTOR_COSTEER_DATA_FOLDER_DEBUG"] = str(source_cache / "debug")
        env["QLIB_DATA_START"] = req.trainStartDate
        env["QLIB_DATA_END"] = req.testEndDate
        env["WORKSPACE_PATH"] = f"{results_base}/workspace_{experiment_id}"
        env["PICKLE_CACHE_FOLDER_PATH_STR"] = f"{results_base}/pickle_cache_{experiment_id}"

        os.makedirs(env["WORKSPACE_PATH"], exist_ok=True)
        os.makedirs(env["PICKLE_CACHE_FOLDER_PATH_STR"], exist_ok=True)
        cleanup_paths = {
            "finished_workspace": env["WORKSPACE_PATH"],
            "finished_pickle_cache": env["PICKLE_CACHE_FOLDER_PATH_STR"],
            "finished_log_root": env["LOG_TRACE_PATH"],
        }

        # Market-specific alias: never redirect the Chinese dataset to US data.
        qlib_data = env.get("QLIB_DATA_DIR", "")
        if qlib_data:
            qlib_symlink_dir = Path.home() / ".qlib" / "qlib_data"
            qlib_symlink_dir.mkdir(parents=True, exist_ok=True)
            if market_mode == "crypto":
                data_link = qlib_symlink_dir / "crypto_data"
            else:
                data_link = qlib_symlink_dir / ("us_data" if env.get("QLIB_REGION") == "us" else "cn_data")
            if data_link.is_symlink():
                if data_link.resolve() != Path(qlib_data).resolve():
                    data_link.unlink()
                    data_link.symlink_to(qlib_data)
            elif not data_link.exists():
                data_link.symlink_to(qlib_data)

        # Build a temporary config with frontend parameter overrides
        base_config_path = PROJECT_ROOT / "configs" / "experiment.yaml"
        config_path_to_use = str(base_config_path)

        try:
            with open(base_config_path, "r", encoding="utf-8") as _f:
                run_cfg = yaml.safe_load(_f) or {}

            # Apply frontend overrides
            if req.numDirections is not None:
                run_cfg.setdefault("planning", {})["num_directions"] = req.numDirections
            if req.maxRounds is not None:
                run_cfg.setdefault("evolution", {})["max_rounds"] = req.maxRounds
            if req.maxLoops is not None:
                run_cfg.setdefault("execution", {})["max_loops"] = req.maxLoops
            if req.factorsPerHypothesis is not None:
                run_cfg.setdefault("factor", {})["factors_per_hypothesis"] = req.factorsPerHypothesis

            valid_frequencies = ("day", "week", "month")
            evaluation_frequencies = list(dict.fromkeys(
                str(value).strip().lower()
                for value in req.evaluationFrequencies
                if str(value).strip().lower() in valid_frequencies
            )) or ["day"]
            env["MINING_EVALUATION_FREQUENCIES"] = ",".join(evaluation_frequencies)
            run_cfg.setdefault("evaluation", {})["frequencies"] = evaluation_frequencies
            task["config"]["evaluationFrequencies"] = evaluation_frequencies

            # Apply parallel execution override from frontend
            if req.parallelEnabled is not None:
                run_cfg.setdefault("evolution", {})["parallel_enabled"] = req.parallelEnabled
                run_cfg.setdefault("execution", {})["parallel_execution"] = req.parallelEnabled

            # Apply quality gate override from frontend
            if req.qualityGateEnabled is not None:
                qg = run_cfg.setdefault("quality_gate", {})
                if req.qualityGateEnabled:
                    # Enable quality gate: enable complexity and redundancy checks (default on), consistency keeps user YAML setting
                    qg.setdefault("complexity_enabled", True)
                    qg.setdefault("redundancy_enabled", True)
                    # Consistency check is expensive, only enable if explicitly enabled in YAML
                    qg.setdefault("consistency_enabled", False)
                else:
                    # Disable quality gate: disable all
                    qg["consistency_enabled"] = False
                    qg["complexity_enabled"] = False
                    qg["redundancy_enabled"] = False

            # Write to a temporary file so the original is untouched
            tmp_dir = Path(env.get("WORKSPACE_PATH", "/tmp"))
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_cfg = tmp_dir / "experiment_override.yaml"
            with open(tmp_cfg, "w", encoding="utf-8") as _f:
                yaml.safe_dump(run_cfg, _f, allow_unicode=True, default_flow_style=False)
            config_path_to_use = str(tmp_cfg)
        except Exception as cfg_err:
            # Fall back to original config if anything fails
            import traceback
            traceback.print_exc()

        # Build CLI args
        cmd = [
            sys.executable, "-m", "quantaalpha.cli", "mine",
            "--direction", req.direction,
            "--config_path", config_path_to_use,
        ]

        task["status"] = "running"
        task["progress"]["phase"] = "planning"
        task["progress"]["message"] = "正在启动实验..."
        task["updatedAt"] = _now()

        await _broadcast(task_id, {
            "type": "progress",
            "taskId": task_id,
            "data": task["progress"],
            "timestamp": _now(),
        })

        # Launch subprocess
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        task["pid"] = proc.pid

        # Stream stdout line by line
        line_count = 0
        current_phase = "planning"

        # Noisy patterns to suppress (shared with backtest)
        _MINING_NOISE = (
            "field data contains nan",
            "common_infra",
            "PyTorch models are skipped",
            "UserWarning: pkg_resources",
            "FutureWarning",
            "UserWarning",
            "Training until validation scores",
            "Did not meet early stopping",
        )

        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            line_count += 1

            # Skip noisy warnings
            if any(p in line for p in _MINING_NOISE):
                continue

            # Detect phase from log messages
            new_phase = current_phase
            if "factor_propose" in line:
                new_phase = "evolving"
            elif "factor_backtest" in line or "backtest" in line.lower():
                new_phase = "backtesting"
            elif "feedback" in line:
                new_phase = "analyzing"
            elif "factor_calculate" in line:
                new_phase = "evolving"
            elif "规划" in line or "planning" in line.lower():
                new_phase = "planning"
            elif "进化完成" in line or "程序执行完成" in line:
                new_phase = "completed"

            if new_phase != current_phase:
                current_phase = new_phase
                task["progress"]["phase"] = current_phase
                task["progress"]["message"] = line[:200]
                task["progress"]["timestamp"] = _now()
                await _broadcast(task_id, {
                    "type": "progress",
                    "taskId": task_id,
                    "data": task["progress"],
                    "timestamp": _now(),
                })

            # Send log every line (throttle to avoid flooding)
            if line_count % 3 == 0 or "INFO" in line or "ERROR" in line or "WARNING" in line:
                level = "info"
                if "ERROR" in line or "Error" in line:
                    level = "error"
                elif "WARNING" in line or "Warning" in line:
                    level = "warning"
                elif "完成" in line or "success" in line.lower():
                    level = "success"

                log_entry = {
                    "id": _gen_id(),
                    "timestamp": _now(),
                    "level": level,
                    "message": line[:500],
                }
                task["logs"].append(log_entry)
                # Keep only last 500 logs in memory
                if len(task["logs"]) > 500:
                    task["logs"] = task["logs"][-500:]

                await _broadcast(task_id, {
                    "type": "log",
                    "taskId": task_id,
                    "data": log_entry,
                    "timestamp": _now(),
                })

            # Extract metrics from log lines like "RankIC=0.0016"
            if "RankIC=" in line:
                try:
                    rank_ic_str = line.split("RankIC=")[1].split(",")[0].split(")")[0]
                    task["metrics"]["rankIc"] = float(rank_ic_str)
                    await _broadcast(task_id, {
                        "type": "metrics",
                        "taskId": task_id,
                        "data": task["metrics"],
                        "timestamp": _now(),
                    })
                except Exception:
                    pass
            
            # Check for factor saving to update top factors list
            if "已保存" in line or "因子" in line:
                _update_mining_metrics(task)
                if task.get("metrics"):
                     await _broadcast(task_id, {
                        "type": "result",
                        "taskId": task_id,
                        "data": {"status": task["status"], "metrics": task["metrics"]},
                        "timestamp": _now(),
                    })

        exit_code = await proc.wait()
        task["pid"] = None

        if exit_code == 0:
            task["status"] = "completed"
            task["progress"]["phase"] = "completed"
            task["progress"]["progress"] = 100
            task["progress"]["message"] = "实验完成"
        else:
            task["status"] = "failed"
            task["progress"]["message"] = f"实验失败 (exit code: {exit_code})"

        task["updatedAt"] = _now()

        # Load final factor count from the library JSON
        # Prefer the library file matching the librarySuffix for this experiment
        _update_mining_metrics(task)

        await _broadcast(task_id, {
            "type": "result",
            "taskId": task_id,
            "data": {"status": task["status"], "metrics": task["metrics"]},
            "timestamp": _now(),
        })

    except Exception as e:
        task["status"] = "failed"
        task["progress"]["message"] = f"Error: {str(e)}"
        task["updatedAt"] = _now()
        await _broadcast(task_id, {
            "type": "error",
            "taskId": task_id,
            "data": {"error": str(e)},
            "timestamp": _now(),
        })
    finally:
        cleanup_enabled = str(
            locals().get("dotenv", {}).get("AUTO_CLEANUP_ENABLED", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        if cleanup_enabled and cleanup_paths:
            try:
                from quantaalpha.utils.cache_cleanup import cleanup_mining_artifacts
                cleanup = await asyncio.to_thread(
                    cleanup_mining_artifacts,
                    PROJECT_ROOT,
                    **cleanup_paths,
                    stale_hours=float(locals().get("dotenv", {}).get("CACHE_RETENTION_HOURS", "24")),
                    log_cache_hours=float(locals().get("dotenv", {}).get("LOG_CACHE_RETENTION_HOURS", "6")),
                    orphan_factor_cache_hours=float(
                        locals().get("dotenv", {}).get("ORPHAN_FACTOR_CACHE_RETENTION_HOURS", "24")
                    ),
                )
                task["cleanup"] = cleanup
                log_entry = {
                    "id": _gen_id(), "timestamp": _now(), "level": "success",
                    "message": (
                        f"自动清理完成：释放 {cleanup['gigabytes_freed']:.3f} GB，"
                        f"清理 {cleanup['removed_count']} 项陈旧缓存"
                    ),
                }
                task["logs"].append(log_entry)
                await _broadcast(task_id, {
                    "type": "log", "taskId": task_id,
                    "data": log_entry, "timestamp": _now(),
                })
            except Exception as cleanup_error:
                task["cleanup"] = {"error": str(cleanup_error)}


# ========================== API Endpoints ==========================

@app.get("/")
async def root():
    return {"message": "QuantaAlpha API", "version": "2.0.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": _now()}


# ---- Mining endpoints ----

@app.post("/api/v1/mining/start", response_model=ApiResponse)
async def start_mining(req: MiningStartRequest):
    """Start a new factor mining experiment."""
    try:
        ordered_dates = [
            datetime.fromisoformat(req.trainStartDate),
            datetime.fromisoformat(req.trainEndDate),
            datetime.fromisoformat(req.validStartDate),
            datetime.fromisoformat(req.validEndDate),
            datetime.fromisoformat(req.testStartDate),
            datetime.fromisoformat(req.testEndDate),
        ]
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"Invalid sample date: {error}")
    if not (
        ordered_dates[0] <= ordered_dates[1] < ordered_dates[2]
        <= ordered_dates[3] < ordered_dates[4] <= ordered_dates[5]
    ):
        raise HTTPException(
            status_code=422,
            detail="Train, validation and test ranges must be ordered and non-overlapping",
        )

    visible_memory_gib = _total_memory_gib()
    resource_note = None
    if 0 < visible_memory_gib < 24 and req.parallelEnabled is not False:
        req.parallelEnabled = False
        resource_note = (
            f"内存保护已启用：WSL 可用总内存约 {visible_memory_gib:.1f} GB，"
            "多个挖掘方向将依次执行，避免并行任务触发 OOM。"
        )

    task_id = _gen_id()
    task = {
        "taskId": task_id,
        "status": "running",
        "config": req.model_dump(),
        "progress": {
            "phase": "parsing",
            "currentRound": 0,
            "totalRounds": req.maxRounds or 3,
            "progress": 0,
            "message": "正在初始化实验...",
            "timestamp": _now(),
        },
        "logs": ([{
            "id": _gen_id(),
            "timestamp": _now(),
            "level": "warning",
            "message": resource_note,
        }] if resource_note else []),
        "metrics": {
            "ic": 0, "icir": 0, "rankIc": 0, "rankIcir": 0,
            "annualReturn": 0, "sharpeRatio": 0, "maxDrawdown": 0,
            "totalFactors": 0, "highQualityFactors": 0,
            "mediumQualityFactors": 0, "lowQualityFactors": 0,
        },
        "result": None,
        "pid": None,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    if resource_note:
        task["config"]["resourceProtection"] = resource_note
    tasks[task_id] = task

    # Launch the mining process in background
    asyncio.create_task(_run_mining(task_id, req))

    return ApiResponse(
        success=True,
        data={"taskId": task_id, "task": task},
        message="实验已启动",
    )


@app.get("/api/v1/mining/{task_id}", response_model=ApiResponse)
async def get_mining_status(task_id: str):
    """Get task status."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return ApiResponse(success=True, data={"task": tasks[task_id]})


@app.delete("/api/v1/mining/{task_id}", response_model=ApiResponse)
async def cancel_mining(task_id: str):
    """Cancel a running mining task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    if task.get("pid"):
        try:
            pid = task["pid"]
            # Try graceful termination first
            os.kill(pid, signal.SIGTERM)
            
            # Wait briefly for cleanup (0.5s)
            for _ in range(5):
                try:
                    os.kill(pid, 0) # Check if alive
                    await asyncio.sleep(0.1)
                except ProcessLookupError:
                    break
            
            # Force kill if still running
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
    task["status"] = "cancelled"
    task["updatedAt"] = _now()
    await _broadcast(task_id, {
        "type": "result",
        "taskId": task_id,
        "data": {"status": "cancelled"},
        "timestamp": _now(),
    })
    return ApiResponse(success=True, message="任务已取消")


@app.get("/api/v1/mining/tasks/list", response_model=ApiResponse)
async def list_tasks():
    """List all tasks."""
    task_list = sorted(tasks.values(), key=lambda t: t["createdAt"], reverse=True)
    return ApiResponse(success=True, data={"tasks": task_list})


# ---- Factor library endpoints ----

@app.get("/api/v1/factors", response_model=ApiResponse)
async def get_factors(
    quality: Optional[str] = Query(None, description="Filter by quality: high/medium/low"),
    search: Optional[str] = Query(None, description="Search by factor name"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    library: Optional[str] = Query(None, description="Specific library file name"),
    marketMode: str = Query("us", pattern="^(us|cn|crypto)$"),
    market: str = Query("sp500", pattern="^(sp500|csi300|csi500|sme_composite|binance_usdm)$"),
):
    """Get factors from the factor library JSON."""
    all_library_paths = _find_factor_jsons()
    library_scopes: List[Dict[str, Any]] = []
    scope_by_name: Dict[str, Dict[str, str]] = {}
    payload_by_name: Dict[str, Dict[str, Any]] = {}
    for path in all_library_paths:
        try:
            loaded_library = _load_factor_library(path)
            payload_by_name[Path(path).name] = loaded_library
            scope = _factor_library_scope(path, loaded_library)
        except Exception:
            scope = _factor_library_scope(path)
        descriptor = {"filename": Path(path).name, **scope}
        library_scopes.append(descriptor)
        scope_by_name[Path(path).name] = scope
    library_paths = [
        path for path in all_library_paths
        if scope_by_name[Path(path).name]["marketMode"] == marketMode
        and scope_by_name[Path(path).name]["market"] == market
    ]
    if not library_paths:
        return ApiResponse(
            success=True,
            data={"factors": [], "total": 0, "limit": limit, "offset": offset,
                  "libraries": [], "libraryScopes": library_scopes,
                  "activeScope": {"marketMode": marketMode, "market": market}},
        )

    factor_records: List[tuple[str, Dict[str, Any], str]] = []
    if library == "__all__":
        # Files are newest first. Keep the newest copy when a factor appears in
        # more than one historical snapshot.
        seen = set()
        for path in library_paths:
            try:
                historical = _load_factor_library(path)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to read factor library: {exc}")
            for factor_id, factor_info in historical.get("factors", {}).items():
                if not isinstance(factor_info, dict):
                    continue
                canonical_id = str(factor_info.get("factor_id") or factor_id).strip()
                expression = str(factor_info.get("factor_expression") or "").strip()
                identity = ("id", canonical_id) if canonical_id else ("expression", expression)
                if identity in seen:
                    continue
                seen.add(identity)
                factor_records.append((factor_id, factor_info, Path(path).name))
        metadata = {
            "total_factors": len(factor_records),
            "library_count": len(library_paths),
            "all_history": True,
            "last_updated": datetime.fromtimestamp(max(os.path.getmtime(path) for path in library_paths)).isoformat(),
        }
    else:
        if library:
            if Path(library).name != library:
                raise HTTPException(status_code=400, detail="Invalid factor library filename")
            lib_path = PROJECT_ROOT / "data" / "factorlib" / library
            if not lib_path.exists():
                legacy_path = PROJECT_ROOT / library
                lib_path = legacy_path if legacy_path.exists() else lib_path
            if lib_path.exists():
                selected_scope = _factor_library_scope(lib_path, _load_factor_library(str(lib_path)))
                if selected_scope["marketMode"] != marketMode or selected_scope["market"] != market:
                    raise HTTPException(status_code=400, detail="Factor library does not belong to the selected market")
        else:
            lib_path = Path(library_paths[0])
        if not lib_path.exists():
            raise HTTPException(status_code=404, detail="Factor library not found")
        try:
            raw = _load_factor_library(str(lib_path))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read factor library: {exc}")
        metadata = raw.get("metadata", {})
        factor_records = [
            (factor_id, factor_info, lib_path.name)
            for factor_id, factor_info in raw.get("factors", {}).items()
            if isinstance(factor_info, dict)
        ]

    # Convert dict to list with quality classification
    factors_list: List[Dict[str, Any]] = []
    for factor_id, factor_info, source_library in factor_records:
        if not isinstance(factor_info, dict):
            continue
        bt = factor_info.get("backtest_results", {})
        factor_market_mode = (
            factor_info.get("market_mode")
            or scope_by_name.get(source_library, {}).get("marketMode", "us")
        )
        quality_assessment = _assess_quality({
            **factor_info,
            "market_mode": factor_market_mode,
        })
        q = quality_assessment["quality"]
        # Extract metrics with proper fallbacks
        # Try specific keys first, then standard ones
        ic = bt.get("IC", bt.get("1day.excess_return_without_cost.information_coefficient", 0))
        icir = bt.get("ICIR", bt.get("1day.excess_return_without_cost.information_coefficient_ir", 0))
        rank_ic = bt.get("Rank IC", bt.get("rank_ic", bt.get("1day.excess_return_without_cost.rank_ic", 0)))
        rank_icir = bt.get("Rank ICIR", bt.get("rank_ic_ir", bt.get("1day.excess_return_without_cost.rank_ic_ir", 0)))
        
        frequency = _factor_frequency(bt)
        portfolio_stats = _portfolio_statistics(bt, frequency)
        asset_pricing = _asset_pricing_statistics(bt, frequency)
        industry_statistics = _industry_statistics(bt, frequency)
        preferred_leg = "long" if factor_market_mode == "cn" else "long_short"
        preferred_portfolio = portfolio_stats.get(preferred_leg, {})
        legacy_annual_return = bt.get("1day.excess_return_with_cost.annualized_return",
                                      bt.get("1day.excess_return_without_cost.annualized_return", 0))
        legacy_max_drawdown = bt.get("1day.excess_return_with_cost.max_drawdown",
                                     bt.get("1day.excess_return_without_cost.max_drawdown", 0))
        legacy_sharpe = bt.get("1day.excess_return_with_cost.information_ratio",
                               bt.get("1day.excess_return_without_cost.information_ratio", 0))

        factor_entry = {
            "factorId": factor_info.get("factor_id", factor_id),
            "factorName": factor_info.get("factor_name", "Unknown"),
            "factorExpression": factor_info.get("factor_expression", ""),
            "factorDescription": factor_info.get("factor_description", ""),
            "factorFormulation": factor_info.get("factor_formulation", ""),
            "llmExplanation": factor_info.get("llm_explanation", {}),
            "quality": q,
            "qualityScore": quality_assessment["score"],
            "qualityAssessment": quality_assessment,
            "backtestResults": bt,
            "splitResults": _valid_factor_split_results(
                factor_info,
                (payload_by_name.get(source_library) or {}).get("metadata", {}),
                factor_market_mode,
            ),
            # Extract key metrics
            "ic": ic,
            "icir": icir,
            "rankIc": rank_ic,
            "rankIcir": rank_icir,
            "frequency": frequency,
            "portfolioStats": portfolio_stats,
            "assetPricing": asset_pricing,
            "industryStatistics": industry_statistics,
            "preferredPortfolioLeg": preferred_leg,
            "annualReturn": preferred_portfolio.get("annualizedNetReturn") if preferred_portfolio.get("annualizedNetReturn") is not None else legacy_annual_return,
            "maxDrawdown": preferred_portfolio.get("maxDrawdown") if preferred_portfolio.get("maxDrawdown") is not None else legacy_max_drawdown,
            "sharpeRatio": preferred_portfolio.get("sharpeRatio") if preferred_portfolio.get("sharpeRatio") is not None else legacy_sharpe,
            "round": factor_info.get("evolution_metadata", {}).get("round", 0)
            if isinstance(factor_info.get("evolution_metadata"), dict) else 0,
            "direction": factor_info.get("evolution_metadata", {}).get("direction_index", "")
            if isinstance(factor_info.get("evolution_metadata"), dict) else "",
            "createdAt": factor_info.get("added_at", ""),
            "sourceLibrary": source_library,
            "marketMode": factor_market_mode,
            "market": factor_info.get("market") or scope_by_name.get(source_library, {}).get("market", "sp500"),
        }
        factors_list.append(factor_entry)

    # Apply filters
    if quality:
        factors_list = [f for f in factors_list if f["quality"] == quality]
    if search:
        search_lower = search.lower()
        factors_list = [
            f for f in factors_list
            if search_lower in f["factorName"].lower()
            or search_lower in f.get("factorDescription", "").lower()
            or search_lower in f.get("factorExpression", "").lower()
        ]

    total = len(factors_list)
    paginated = factors_list[offset: offset + limit]

    # Available library files
    all_libs = [Path(p).name for p in library_paths]

    return ApiResponse(
        success=True,
        data={
            "factors": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
            "metadata": metadata,
            "libraries": all_libs,
            "libraryScopes": library_scopes,
            "activeScope": {"marketMode": marketMode, "market": market},
        },
    )


# ---- Factor cache endpoints ----
# IMPORTANT: These must be registered BEFORE /api/v1/factors/{factor_id}
# otherwise FastAPI matches "cache-status" as a factor_id parameter.


def _correlation_factor_records(library: Optional[str], factor_ids: List[str]) -> tuple[List[Dict[str, Any]], List[Path]]:
    requested = list(dict.fromkeys(str(value) for value in factor_ids))
    requested_set = set(requested)
    library_paths = [Path(value) for value in _find_factor_jsons()]
    if not library_paths:
        raise HTTPException(status_code=404, detail="No factor libraries found")
    if library and library != "__all__":
        if Path(library).name != library:
            raise HTTPException(status_code=400, detail="Invalid factor library filename")
        selected = PROJECT_ROOT / "data" / "factorlib" / library
        if not selected.exists():
            legacy = PROJECT_ROOT / library
            selected = legacy if legacy.exists() else selected
        if not selected.exists():
            raise HTTPException(status_code=404, detail="Factor library not found")
        library_paths = [selected]

    found: Dict[str, Dict[str, Any]] = {}
    used_paths: List[Path] = []
    for path in library_paths:
        raw = _load_factor_library(str(path))
        used = False
        for key, info in (raw.get("factors", {}) or {}).items():
            if not isinstance(info, dict):
                continue
            factor_id = str(info.get("factor_id") or key)
            if factor_id in requested_set and factor_id not in found:
                record = dict(info)
                record["factor_id"] = factor_id
                found[factor_id] = record
                used = True
        if used:
            used_paths.append(path)
        if len(found) == len(requested_set):
            break
    records = [found[factor_id] for factor_id in requested if factor_id in found]
    if len(records) < 2:
        raise HTTPException(status_code=400, detail="At least two requested factors were not found")
    return records, used_paths


@app.post("/api/v1/factors/correlation", response_model=ApiResponse)
async def factor_correlation(req: FactorCorrelationRequest):
    """Mean monthly cross-sectional factor correlation from cached factor values."""
    dotenv = _load_dotenv_dict()
    start_date = req.startDate or dotenv.get("TEST_START_DATE", "2015-01-01")
    end_date = req.endDate or dotenv.get("TEST_END_DATE", "2025-12-31")
    records, library_paths = _correlation_factor_records(req.library, req.factorIds)

    # Correlation should not silently exclude formula-backed factors merely
    # because their old workspace/cache was cleaned. Rebuild missing values
    # from the stored expression and persist the stable cache for reuse.
    factor_cache_dir = PROJECT_ROOT / "data" / "results" / "factor_cache"
    missing_records = []
    for record in records:
        expression = str(record.get("factor_expression") or "").strip()
        stable = factor_cache_dir / f"{hashlib.md5(expression.encode()).hexdigest()}.pkl" if expression else None
        h5_raw = (record.get("cache_location") or {}).get("result_h5_path")
        h5_path = Path(h5_raw) if h5_raw else None
        if not ((stable and stable.exists()) or (h5_path and h5_path.exists())):
            missing_records.append(record)
    recomputed_names = []
    if missing_records:
        from quantaalpha.factors.split_evaluation import ensure_factor_signal_cache
        for record in missing_records:
            try:
                await asyncio.to_thread(
                    ensure_factor_signal_cache,
                    record,
                    PROJECT_ROOT,
                    dotenv,
                )
                recomputed_names.append(str(record.get("factor_name") or record.get("factor_id") or "factor"))
            except Exception as exc:
                record["cache_recompute_error"] = str(exc)

    signature = {
        "factor_ids": [record["factor_id"] for record in records],
        "expressions": [record.get("factor_expression", "") for record in records],
        "libraries": [(str(path), path.stat().st_mtime_ns) for path in library_paths],
        "method": req.method,
        "start": start_date,
        "end": end_date,
        "version": 1,
    }
    cache_key = hashlib.sha256(
        json.dumps(signature, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    cache_dir = PROJECT_ROOT / "data" / "results" / "factor_correlation_cache"
    cache_file = cache_dir / f"{cache_key}.json"
    if cache_file.exists():
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        payload["cacheHit"] = True
        return ApiResponse(success=True, data=payload)

    from quantaalpha.factors.correlation import compute_factor_correlation
    try:
        payload = await asyncio.to_thread(
            compute_factor_correlation,
            records,
            start_date,
            end_date,
            req.method,
            PROJECT_ROOT / "data" / "results" / "factor_cache",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    payload["cacheHit"] = False
    payload["recomputedFactors"] = recomputed_names
    return ApiResponse(success=True, data=payload)


@app.get("/api/v1/factors/cache-status", response_model=ApiResponse)
async def get_cache_status(
    library: Optional[str] = Query(None, description="Factor library JSON filename"),
):
    """Check cache status of factors in the specified factor library."""
    if library:
        lib_path = str(PROJECT_ROOT / "data" / "factorlib" / library)
        if not Path(lib_path).exists():
            alt = str(PROJECT_ROOT / library)
            if Path(alt).exists():
                lib_path = alt
    else:
        jsons = _find_factor_jsons()
        if not jsons:
            return ApiResponse(success=True, data={
                "total": 0, "h5_cached": 0, "md5_cached": 0,
                "need_compute": 0, "factors": [],
            })
        lib_path = jsons[0]

    if not Path(lib_path).exists():
        raise HTTPException(status_code=404, detail=f"Factor library not found: {library}")

    # Import from core library
    from quantaalpha.factors.library import FactorLibraryManager
    result = FactorLibraryManager.check_cache_status(lib_path)
    return ApiResponse(success=True, data=result)


@app.post("/api/v1/factors/warm-cache", response_model=ApiResponse)
async def warm_cache(
    library: Optional[str] = Query(None, description="Factor library JSON filename"),
):
    """Batch sync from result.h5 to MD5 cache directory."""
    if library:
        lib_path = str(PROJECT_ROOT / "data" / "factorlib" / library)
        if not Path(lib_path).exists():
            alt = str(PROJECT_ROOT / library)
            if Path(alt).exists():
                lib_path = alt
    else:
        jsons = _find_factor_jsons()
        if not jsons:
            return ApiResponse(success=False, error="未找到因子库文件")
        lib_path = jsons[0]

    if not Path(lib_path).exists():
        raise HTTPException(status_code=404, detail=f"Factor library not found: {library}")

    from quantaalpha.factors.library import FactorLibraryManager
    result = FactorLibraryManager.warm_cache_from_json(lib_path)
    # Build a clear message
    parts = []
    if result['synced']:
        parts.append(f"新同步 {result['synced']} 个")
    if result.get('already_cached'):
        parts.append(f"已有缓存 {result['already_cached']} 个")
    if result.get('no_source'):
        parts.append(f"无H5源 {result['no_source']} 个(回测时从表达式计算)")
    if result['failed']:
        parts.append(f"失败 {result['failed']} 个")
    msg = "，".join(parts) if parts else "无需操作"
    return ApiResponse(
        success=True,
        data=result,
        message=msg,
    )


# ---- Factor library list endpoint (must be BEFORE {factor_id} route) ----

@app.get("/api/v1/factors/libraries", response_model=ApiResponse)
async def list_factor_libraries():
    """List all factor library JSON files in the project root."""
    libs = [Path(p).name for p in _find_factor_jsons()]
    return ApiResponse(success=True, data={"libraries": libs})


@app.post("/api/v1/factors/delete", response_model=ApiResponse)
async def delete_factors(req: FactorDeleteRequest):
    """Delete selected factors atomically from one library or all history."""
    requested = list(dict.fromkeys(req.factorIds))
    requested_set = set(requested)
    if req.library == "__all__":
        library_paths = [Path(value) for value in _find_factor_jsons()]
        if req.marketMode and req.market:
            library_paths = [
                path for path in library_paths
                if (scope := _factor_library_scope(path, _load_factor_library(str(path))))["marketMode"] == req.marketMode
                and scope["market"] == req.market
            ]
    elif req.library:
        if Path(req.library).name != req.library:
            raise HTTPException(status_code=400, detail="Invalid factor library filename")
        library_paths = [PROJECT_ROOT / "data" / "factorlib" / req.library]
    else:
        libraries = _find_factor_jsons()
        if not libraries:
            raise HTTPException(status_code=404, detail="No factor library found")
        library_paths = [Path(libraries[0])]

    deleted_ids = set()
    changed_libraries = []
    remaining_total = 0
    for lib_path in library_paths:
        if not lib_path.exists():
            continue
        raw = _load_factor_library(str(lib_path))
        factors = raw.get("factors", {})
        keys_to_delete = [
            key for key, info in factors.items()
            if key in requested_set
            or (isinstance(info, dict) and str(info.get("factor_id") or "") in requested_set)
        ]
        if keys_to_delete:
            for key in keys_to_delete:
                info = factors.pop(key)
                deleted_ids.add(str(info.get("factor_id") or key) if isinstance(info, dict) else str(key))
            metadata = raw.setdefault("metadata", {})
            metadata["total_factors"] = len(factors)
            metadata["last_updated"] = _now()
            temp_path = lib_path.with_suffix(lib_path.suffix + ".tmp")
            temp_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp_path, lib_path)
            changed_libraries.append(lib_path.name)
        remaining_total += len(factors)
    if not deleted_ids:
        raise HTTPException(status_code=404, detail="Selected factors were not found")
    deleted = [factor_id for factor_id in requested if factor_id in deleted_ids]
    return ApiResponse(success=True, data={
        "deleted": deleted,
        "deletedCount": len(deleted),
        "remaining": remaining_total,
        "library": req.library or library_paths[0].name,
        "changedLibraries": changed_libraries,
    })


@app.get("/api/v1/factors/{factor_id}/split-evaluation", response_model=ApiResponse)
async def get_factor_split_evaluation(
    factor_id: str,
    split: str = Query("test", pattern="^(train|valid|test)$"),
    library: Optional[str] = Query(None, description="Specific library file name"),
    force: bool = Query(False),
):
    """Calculate one split lazily; held-out test is unavailable while mining runs."""
    if split == "test" and any(
        task.get("status") in {"pending", "running"}
        for task in tasks.values()
    ):
        raise HTTPException(
            status_code=409,
            detail="测试集保持锁定：请等待本轮因子挖掘与进化筛选完成",
        )
    if library:
        if Path(library).name != library:
            raise HTTPException(status_code=400, detail="Invalid factor library filename")
        candidates = [PROJECT_ROOT / "data" / "factorlib" / library]
    else:
        candidates = [Path(value) for value in _find_factor_jsons()]
    library_path = None
    library_payload = None
    factor_info = None
    for candidate in candidates:
        if not candidate.exists():
            continue
        raw = _load_factor_library(str(candidate))
        if factor_id in (raw.get("factors") or {}):
            library_path = candidate
            library_payload = raw
            factor_info = raw["factors"][factor_id]
            break
    if library_path is None:
        raise HTTPException(status_code=404, detail="Factor not found")

    evaluation_env = _load_dotenv_dict()
    scope = _factor_library_scope(library_path, library_payload)
    evaluation_env["MARKET_MODE"] = scope["marketMode"]
    evaluation_env["QLIB_MARKET"] = scope["market"]
    date_prefix = "CRYPTO" if scope["marketMode"] == "crypto" else ("CN" if scope["marketMode"] == "cn" else "US")
    for stem in ("TRAIN", "VALID", "TEST"):
        for boundary in ("START", "END"):
            generic_key = f"{stem}_{boundary}_DATE"
            specific_key = f"{date_prefix}_{generic_key}"
            if evaluation_env.get(specific_key):
                evaluation_env[generic_key] = evaluation_env[specific_key]
    if scope["marketMode"] == "crypto":
        evaluation_env["QLIB_REGION"] = "us"
        evaluation_env["DATA_SOURCE"] = "binance_futures"
        evaluation_env["QLIB_DATA_DIR"] = evaluation_env.get(
            "CRYPTO_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "binance_usdm")
        )
    elif scope["marketMode"] == "cn":
        evaluation_env["QLIB_REGION"] = "cn"
        evaluation_env["QLIB_DATA_DIR"] = evaluation_env.get(
            "CN_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "cn_market")
        )
    else:
        evaluation_env["QLIB_REGION"] = "us"
        evaluation_env["QLIB_DATA_DIR"] = evaluation_env.get(
            "WRDS_QLIB_DATA_DIR", evaluation_env.get("QLIB_DATA_DIR", "")
        )

    metadata = (library_payload or {}).get("metadata", {})
    factor_metadata = factor_info.get("metadata", {}) if isinstance(factor_info, dict) else {}
    split_windows = factor_metadata.get("split_windows") or metadata.get("split_windows") or {}
    key_map = {
        "train": ("TRAIN_START_DATE", "TRAIN_END_DATE"),
        "valid": ("VALID_START_DATE", "VALID_END_DATE"),
        "test": ("TEST_START_DATE", "TEST_END_DATE"),
    }
    for split_name, keys in key_map.items():
        window = split_windows.get(split_name) if isinstance(split_windows, dict) else None
        if isinstance(window, (list, tuple)) and len(window) == 2 and all(window):
            evaluation_env[keys[0]], evaluation_env[keys[1]] = str(window[0]), str(window[1])
    if metadata.get("evaluation_frequencies"):
        evaluation_env["MINING_EVALUATION_FREQUENCIES"] = str(metadata["evaluation_frequencies"])
    stored_filters = metadata.get("market_filters") or {}
    for stored_key, env_key in (
        ("exclude_st", "CN_EXCLUDE_ST"),
        ("exclude_new_stocks", "CN_EXCLUDE_NEW_STOCKS"),
        ("exclude_chinext", "CN_EXCLUDE_CHINEXT"),
        ("exclude_star", "CN_EXCLUDE_STAR"),
        ("exclude_bse", "CN_EXCLUDE_BSE"),
        ("new_stock_min_trading_days", "CN_NEW_STOCK_MIN_TRADING_DAYS"),
    ):
        if stored_key in stored_filters:
            evaluation_env[env_key] = str(stored_filters[stored_key])

    # Libraries created before split metadata was introduced can recover the
    # exact settings from the still-known mining task that produced them.
    filename = library_path.name
    for task in tasks.values():
        config = task.get("config", {})
        suffix = config.get("librarySuffix")
        if not suffix or filename != f"all_factors_library_{suffix}.json":
            continue
        for camel, env_key in (
            ("trainStartDate", "TRAIN_START_DATE"), ("trainEndDate", "TRAIN_END_DATE"),
            ("validStartDate", "VALID_START_DATE"), ("validEndDate", "VALID_END_DATE"),
            ("testStartDate", "TEST_START_DATE"), ("testEndDate", "TEST_END_DATE"),
        ):
            if config.get(camel):
                evaluation_env[env_key] = str(config[camel])
        evaluation_env["MINING_EVALUATION_FREQUENCIES"] = ",".join(
            config.get("evaluationFrequencies") or ["day", "week", "month"]
        )
        for camel, env_key in (
            ("excludeSt", "CN_EXCLUDE_ST"), ("excludeNewStocks", "CN_EXCLUDE_NEW_STOCKS"),
            ("excludeChiNext", "CN_EXCLUDE_CHINEXT"), ("excludeStar", "CN_EXCLUDE_STAR"),
            ("excludeBse", "CN_EXCLUDE_BSE"),
        ):
            if camel in config:
                evaluation_env[env_key] = "true" if config[camel] else "false"
        if config.get("newStockMinTradingDays") is not None:
            evaluation_env["CN_NEW_STOCK_MIN_TRADING_DAYS"] = str(config["newStockMinTradingDays"])
        break

    from quantaalpha.factors.split_evaluation import evaluate_factor_split
    try:
        cached_result = (factor_info.get("split_results") or {}).get(split) if isinstance(factor_info, dict) else None
        start_key, end_key = {
            "train": ("TRAIN_START_DATE", "TRAIN_END_DATE"),
            "valid": ("VALID_START_DATE", "VALID_END_DATE"),
            "test": ("TEST_START_DATE", "TEST_END_DATE"),
        }[split]
        cached_before = bool(
            not force
            and isinstance(cached_result, dict)
            and str(cached_result.get("startDate")) == str(evaluation_env.get(start_key))
            and str(cached_result.get("endDate")) == str(evaluation_env.get(end_key))
        )
        result = await asyncio.to_thread(
            evaluate_factor_split,
            library_path,
            factor_id,
            split,
            PROJECT_ROOT,
            force=force,
            environment=evaluation_env,
        )
        return ApiResponse(success=True, data={
            "evaluation": result,
            "cacheHit": cached_before,
        })
    except (ValueError, FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/factors/{factor_id}", response_model=ApiResponse)
async def get_factor_detail(
    factor_id: str,
    library: Optional[str] = Query(None, description="Specific library file name"),
):
    """Get full detail of a single factor."""
    if library:
        if Path(library).name != library:
            raise HTTPException(status_code=400, detail="Invalid factor library filename")
        jsons = [str(PROJECT_ROOT / "data" / "factorlib" / library)]
    else:
        jsons = _find_factor_jsons()
    for lib_path in jsons:
        try:
            raw = _load_factor_library(lib_path)
            factors = raw.get("factors", {})
            if factor_id in factors:
                info = dict(factors[factor_id])
                scope = _factor_library_scope(lib_path, raw)
                info["split_results"] = _valid_factor_split_results(
                    info,
                    raw.get("metadata", {}),
                    scope["marketMode"],
                )
                assessment = _assess_quality(info)
                info["quality"] = assessment["quality"]
                info["qualityScore"] = assessment["score"]
                info["qualityAssessment"] = assessment
                return ApiResponse(success=True, data={"factor": info})
        except Exception:
            continue
    raise HTTPException(status_code=404, detail="Factor not found")


# ---- Backtest endpoints ----

@app.get("/api/v1/backtest/config", response_model=ApiResponse)
async def get_backtest_config():
    """Return the effective, non-secret market settings shown by the UI."""
    config_path = PROJECT_ROOT / "configs" / "backtest.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    data_config = config.get("data", {})
    portfolio_config = config.get("backtest", {}).get("backtest", {})
    dotenv = _load_dotenv_dict()
    market_mode = dotenv.get("MARKET_MODE", "us")
    if market_mode not in {"us", "cn", "crypto"}:
        market_mode = "us"
    date_prefix = "CRYPTO" if market_mode == "crypto" else ("CN" if market_mode == "cn" else "US")

    def market_date(key: str) -> Optional[str]:
        return dotenv.get(f"{date_prefix}_{key}") or dotenv.get(key)
    wrds_root = Path(dotenv.get("WRDS_ROOT", "/mnt/d/桌面文件/US stock research/wrds"))
    kelly_panel = wrds_root / "_quantaalpha_cache" / "kelly_153_sp500.parquet"
    kelly_report = PROJECT_ROOT / "data" / "kelly" / "jkp_sp500_missingness_1987.json"
    kelly_status: Dict[str, Any] = {
        "ready": kelly_panel.exists() and kelly_report.exists(),
        "panelPath": str(kelly_panel),
        "reportPath": str(kelly_report),
        "factorCount": 153,
        "thresholdCounts": {},
    }
    if kelly_report.exists():
        try:
            report_payload = json.loads(kelly_report.read_text(encoding="utf-8"))
            summary = report_payload.get("summary", {})
            kelly_status.update({
                "factorCount": summary.get("factor_count", 153),
                "memberMonths": summary.get("sp500_member_months"),
                "modelRows": summary.get("model_rows_with_forward_return"),
                "startMonth": summary.get("start_month"),
                "endMonth": summary.get("end_month"),
                "thresholdCounts": summary.get("threshold_counts", {}),
                "factors": report_payload.get("factors", []),
            })
        except Exception:
            pass
    return ApiResponse(success=True, data={
        "region": market_mode,
        "market": dotenv.get("DEFAULT_MARKET", data_config.get("market", "sp500")),
        "startTime": portfolio_config.get("start_time") or data_config.get("start_time"),
        "endTime": portfolio_config.get("end_time") or data_config.get("end_time"),
        "benchmark": (
            {"csi300": "SH000300", "csi500": "SH000905", "sme_composite": "SZ399101"}.get(
                dotenv.get("DEFAULT_MARKET", "csi300"), "SH000300"
            ) if dotenv.get("MARKET_MODE") == "cn" else portfolio_config.get("benchmark", "")
        ),
        "trainStartDate": market_date("TRAIN_START_DATE"),
        "trainEndDate": market_date("TRAIN_END_DATE"),
        "validStartDate": market_date("VALID_START_DATE"),
        "validEndDate": market_date("VALID_END_DATE"),
        "testStartDate": market_date("TEST_START_DATE"),
        "testEndDate": market_date("TEST_END_DATE"),
        "supportedModels": ["lightgbm", "pls5", "lasso"],
        "kelly": kelly_status,
    })

@app.post("/api/v1/backtest/start", response_model=ApiResponse)
async def start_backtest(req: BacktestStartRequest):
    """Start an independent backtest."""
    task_id = _gen_id()
    config_path = req.configPath or str(PROJECT_ROOT / "configs" / "backtest.yaml")

    task = {
        "taskId": task_id,
        "status": "running",
        "type": "backtest",
        "config": {**req.model_dump(), "configPath": config_path},
        "progress": {
            "phase": "backtesting",
            "currentRound": 0,
            "totalRounds": 1,
            "progress": 0,
            "message": "正在启动回测...",
            "timestamp": _now(),
        },
        "logs": [],
        "metrics": {},
        "result": None,
        "pid": None,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    tasks[task_id] = task

    # Launch backtest in background
    asyncio.create_task(_run_backtest(task_id, req, config_path))
    return ApiResponse(
        success=True,
        data={"taskId": task_id, "task": task},
        message="回测已启动",
    )


@app.get("/api/v1/backtest/latest", response_model=ApiResponse)
async def latest_backtest():
    """Return the most recently created backtest so the UI can recover after refresh."""
    candidates = [task for task in tasks.values() if task.get("type") == "backtest"]
    if candidates:
        latest = max(candidates, key=lambda task: task.get("createdAt", ""))
        return ApiResponse(success=True, data={"task": latest})

    # Backend restarts clear the in-memory task table. Completed backtests are
    # durable JSON artifacts, so rebuild a display task from the newest one.
    result_files = list((PROJECT_ROOT / "data").glob("**/*_backtest_metrics.json"))
    if not result_files:
        raise HTTPException(status_code=404, detail="No backtest task found")
    result_path = max(result_files, key=lambda path: path.stat().st_mtime)
    saved = json.loads(result_path.read_text(encoding="utf-8"))
    created = datetime.fromtimestamp(result_path.stat().st_mtime).isoformat()
    restored = {
        "taskId": f"saved-{result_path.stem}",
        "status": "completed",
        "type": "backtest",
        "config": saved.get("config", {}),
        "progress": {
            "phase": "completed", "currentRound": 1, "totalRounds": 1,
            "progress": 100, "message": "已恢复最近一次回测结果", "timestamp": created,
        },
        "logs": [],
        "metrics": saved.get("metrics", {}),
        "result": str(result_path),
        "pid": None,
        "createdAt": created,
        "updatedAt": created,
    }
    return ApiResponse(success=True, data={"task": restored})


@app.get("/api/v1/backtest/{task_id}", response_model=ApiResponse)
async def get_backtest_status(task_id: str):
    """Get backtest task status and results."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return ApiResponse(success=True, data={"task": tasks[task_id]})


@app.delete("/api/v1/backtest/{task_id}", response_model=ApiResponse)
async def cancel_backtest(task_id: str):
    """Cancel a running backtest task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    if task.get("pid"):
        try:
            os.kill(task["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
    task["status"] = "cancelled"
    task["updatedAt"] = _now()
    await _broadcast(task_id, {
        "type": "result",
        "taskId": task_id,
        "data": {"status": "cancelled"},
        "timestamp": _now(),
    })
    return ApiResponse(success=True, message="回测已取消")


async def _run_backtest(task_id: str, req: BacktestStartRequest, config_path: str):
    """Run the independent backtest (V2) as a subprocess."""
    task = tasks[task_id]
    temporary_factor_json: Optional[Path] = None
    temporary_config_path: Optional[Path] = None
    try:
        env = os.environ.copy()
        dotenv = _load_dotenv_dict()
        env.update(dotenv)
        # MLflow 3.x disables the legacy filesystem tracking store unless this
        # compatibility flag is present in the *backtest subprocess* itself.
        # The mining subprocess already receives it, but standalone backtests
        # use this separate launcher path.
        env["MLFLOW_ALLOW_FILE_STORE"] = "true"

        with open(config_path, "r", encoding="utf-8") as config_file:
            effective_config = yaml.safe_load(config_file) or {}
        source = dotenv.get("DATA_SOURCE", "qlib")
        market_mode = dotenv.get("MARKET_MODE", "us")
        default_market = "csi300" if market_mode == "cn" else ("binance_usdm" if market_mode == "crypto" else "sp500")
        market = dotenv.get("DEFAULT_MARKET", default_market)
        if req.portfolioOptimization and (market_mode != "us" or req.portfolioMode != "long_short"):
            raise ValueError("MAXSER-PR portfolio optimization currently requires US Long-Short mode")
        if req.factorSource == "kelly_jkp" and market_mode != "us":
            raise ValueError("WRDS Kelly 153 only supports the US S&P 500 market")
        if market_mode == "crypto":
            source = "binance_futures"
            market = "binance_usdm"
            provider = dotenv.get("CRYPTO_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "binance_usdm"))
            # The factor calculator prioritizes QLIB_DATA_DIR over the YAML
            # provider.  Override both so a Crypto backtest cannot silently
            # reuse the US WRDS provider inherited from .env.
            env["QLIB_DATA_DIR"] = provider
            env["QLIB_PROVIDER_URI"] = provider
            env["MARKET_MODE"] = "crypto"
            env["QLIB_MARKET"] = "binance_usdm"
            env["DATA_SOURCE"] = "binance_futures"
            effective_config.setdefault("data", {}).update({"provider_uri": provider, "region": "us", "market": market, "market_mode": "crypto"})
            effective_config.setdefault("dataset", {})["label"] = "Ref($close, -2) / Ref($close, -1) - 1"
            backtest_cfg = effective_config.setdefault("backtest", {}).setdefault("backtest", {})
            backtest_cfg["benchmark"] = None
            exchange = backtest_cfg.setdefault("exchange_kwargs", {})
            exchange.update({"limit_threshold": None, "trade_unit": None})
        elif market_mode == "cn":
            source = "cn_duckdb"
            provider = dotenv.get("CN_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "cn_market"))
            benchmark = {"csi300": "SH000300", "csi500": "SH000905", "sme_composite": "SZ399101"}.get(market, "SH000300")
            effective_config.setdefault("data", {}).update({"provider_uri": provider, "region": "cn", "market": market})
            effective_config.setdefault("dataset", {})["label"] = "Ref($close, -2) / Ref($close, -1) - 1"
            effective_config.setdefault("backtest", {}).setdefault("backtest", {})["benchmark"] = benchmark
            exchange = effective_config["backtest"]["backtest"].setdefault("exchange_kwargs", {})
            exchange.update({"limit_threshold": 0.1, "trade_unit": 100})
        else:
            provider = dotenv.get("WRDS_QLIB_DATA_DIR") if source == "wrds" else dotenv.get("QLIB_DATA_DIR")
            effective_config.setdefault("data", {}).update({"region": "us", "market": "sp500"})
            effective_config.setdefault("dataset", {})["label"] = "Ref($ret_total, -1)"
        if provider:
            effective_config.setdefault("data", {})["provider_uri"] = provider
        date_prefix = "CRYPTO" if market_mode == "crypto" else ("CN" if market_mode == "cn" else "US")

        def market_date(key: str) -> Optional[str]:
            return dotenv.get(f"{date_prefix}_{key}") or dotenv.get(key)

        def us_date(key: str) -> Optional[str]:
            return dotenv.get(f"US_{key}") or dotenv.get(key)

        segment_keys = {
            "train": ("TRAIN_START_DATE", "TRAIN_END_DATE"),
            "valid": ("VALID_START_DATE", "VALID_END_DATE"),
            "test": ("TEST_START_DATE", "TEST_END_DATE"),
        }
        segments = effective_config.setdefault("dataset", {}).setdefault("segments", {})
        for segment, (start_key, end_key) in segment_keys.items():
            start = market_date(start_key)
            end = market_date(end_key)
            if start and end:
                segments[segment] = [start, end]
        test_segment = segments.get("test")
        if isinstance(test_segment, list) and len(test_segment) == 2:
            effective_config.setdefault("data", {})["start_time"] = segments.get("train", test_segment)[0]
            effective_config.setdefault("data", {})["end_time"] = test_segment[1]
            effective_config.setdefault("backtest", {}).setdefault("backtest", {})["start_time"] = test_segment[0]
            effective_config.setdefault("backtest", {}).setdefault("backtest", {})["end_time"] = test_segment[1]
        override_dir = Path(dotenv.get("DATA_RESULTS_DIR", str(PROJECT_ROOT / "data" / "results"))) / "backtest_overrides"
        override_dir.mkdir(parents=True, exist_ok=True)
        override_path = override_dir / f"{task_id}.yaml"
        temporary_config_path = override_path
        override_path.write_text(yaml.safe_dump(effective_config, sort_keys=False), encoding="utf-8")
        config_path = str(override_path)
        task["config"]["configPath"] = config_path

        # Custom/Combined always consume the deduplicated total library for the
        # active market. Individual timestamped snapshots remain browsing and
        # audit artifacts, not model-input selectors.
        if req.factorSource != "kelly_jkp":
            factor_json_path = override_dir / f"{task_id}_{market_mode}_{market}_total_factors.json"
            temporary_factor_json = factor_json_path
            aggregate = _build_total_factor_library(market_mode, market, factor_json_path)
            task["config"]["factorJson"] = factor_json_path.name
            task["config"]["factorCount"] = len(aggregate["factors"])
            task["config"]["factorScope"] = f"{market_mode}/{market}/all-history"
        else:
            factor_json_input = req.factorJson
            factor_json_path = Path(factor_json_input) if factor_json_input else Path()
        factor_json_str = str(factor_json_path)

        # --- Find the correct Python executable ---
        # Prefer the conda env that has qlib installed
        conda_env = dotenv.get("CONDA_ENV_NAME", "quantaalpha")
        python_bin = sys.executable  # fallback

        # Dynamically detect conda base path (portable, no hardcoded paths)
        conda_prefixes = [os.path.expanduser(f"~/.conda/envs/{conda_env}")]
        try:
            import subprocess as _sp
            conda_base = _sp.check_output(
                ["conda", "info", "--base"], text=True, timeout=5
            ).strip()
            conda_prefixes.insert(0, os.path.join(conda_base, "envs", conda_env))
        except Exception:
            pass
        # Also check CONDA_PREFIX if we're already in the right env
        if os.environ.get("CONDA_PREFIX"):
            conda_prefixes.insert(0, os.environ["CONDA_PREFIX"])

        for prefix in conda_prefixes:
            candidate_bin = Path(prefix) / "bin" / "python"
            if candidate_bin.exists():
                python_bin = str(candidate_bin)
                break

        # Build CLI command
        selected_model = req.model or req.kellyModel
        retrain_months = req.retrainMonths or req.kellyRetrainMonths
        min_train_years = req.minTrainYears or req.kellyMinTrainYears
        if market_mode == "crypto":
            train_segment = segments.get("train") or []
            test_segment = segments.get("test") or []
            if len(train_segment) == 2 and len(test_segment) == 2:
                train_start = datetime.fromisoformat(str(train_segment[0])).date()
                test_start = datetime.fromisoformat(str(test_segment[0])).date()
                full_years = test_start.year - train_start.year - (
                    (test_start.month, test_start.day) < (train_start.month, train_start.day)
                )
                # Keep a one-year margin for factor lookbacks and forward
                # labels. With the default 2020/2024 split this becomes 3.
                crypto_history_limit = max(1, full_years - 1)
                min_train_years = min(int(min_train_years), crypto_history_limit)
        task["config"]["model"] = selected_model
        task["config"]["retrainMonths"] = retrain_months
        task["config"]["minTrainYears"] = min_train_years
        if req.factorSource == "kelly_jkp":
            wrds_root = Path(dotenv.get("WRDS_ROOT", "/mnt/d/桌面文件/US stock research/wrds"))
            panel_path = wrds_root / "_quantaalpha_cache" / "kelly_153_sp500.parquet"
            if not panel_path.exists():
                raise FileNotFoundError(
                    f"Kelly S&P 500 panel not found: {panel_path}. Build the Kelly cache first."
                )
            output_dir = Path(
                effective_config.get("experiment", {}).get(
                    "output_dir", "data/results/backtest_v2_results"
                )
            )
            if not output_dir.is_absolute():
                output_dir = PROJECT_ROOT / output_dir
            cmd = [
                python_bin, "-m", "quantaalpha.backtest.kelly_expanding",
                "--panel", str(panel_path),
                "--output-dir", str(output_dir),
                "--missing-threshold", str(req.kellyMissingThreshold),
                "--model", selected_model,
                "--retrain-months", str(retrain_months),
                "--min-train-years", str(min_train_years),
                "--train-start", us_date("TRAIN_START_DATE") or "1987-01-01",
                "--train-end", us_date("TRAIN_END_DATE") or "2010-12-31",
                "--valid-start", us_date("VALID_START_DATE") or "2011-01-01",
                "--valid-end", us_date("VALID_END_DATE") or "2014-12-31",
                "--test-start", us_date("TEST_START_DATE") or "2015-01-01",
                "--test-end", us_date("TEST_END_DATE") or "2025-12-31",
                "--portfolio-mode", req.portfolioMode,
                "--transaction-cost", str(
                    effective_config.get("backtest", {})
                    .get("long_short", {})
                    .get("transaction_cost", 0.0005)
                ),
            ]
            if req.portfolioOptimization:
                cmd.append("--portfolio-optimization")
            if req.correlationPruning:
                cmd.extend(["--correlation-pruning", "--correlation-threshold", str(req.correlationThreshold)])
        else:
            cmd = [
                python_bin, "-m", "quantaalpha.backtest.run_backtest",
                "-c", config_path,
                "--factor-source", req.factorSource,
                "--factor-json", factor_json_str,
                "--portfolio-mode", req.portfolioMode,
                "--quality-filter", req.qualityFilter,
                "--model", selected_model,
                "--retrain-months", str(retrain_months),
                "--min-train-years", str(min_train_years),
                "-v",
            ]
            if req.portfolioOptimization:
                cmd.append("--portfolio-optimization")
            if req.correlationPruning:
                cmd.extend(["--correlation-pruning", "--correlation-threshold", str(req.correlationThreshold)])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        task["pid"] = proc.pid

        # Noisy warnings from Qlib / dependencies that can be safely suppressed
        _NOISY_PATTERNS = (
            "field data contains nan",
            "common_infra",
            "PyTorch models are skipped",
            "UserWarning: pkg_resources",
            "Training until validation scores",
            "FutureWarning",
            "UserWarning",
            "Did not meet early stopping",
            "num_leaves is set=",
        )

        # --- Stream stdout ---
        log_entry = None
        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue

            # Skip noisy repeated warnings
            if any(p in line for p in _NOISY_PATTERNS):
                continue

            level = "info"
            if "ERROR" in line or "Error" in line:
                level = "error"
            elif "WARNING" in line or "Warning" in line:
                level = "warning"
            elif "完成" in line or "success" in line.lower() or "✓" in line:
                level = "success"

            log_entry = {
                "id": _gen_id(),
                "timestamp": _now(),
                "level": level,
                "message": line[:500],
            }
            task["logs"].append(log_entry)
            if len(task["logs"]) > 2000:
                task["logs"] = task["logs"][-2000:]

            # Broadcast log to WebSocket
            await _broadcast(task_id, {
                "type": "log",
                "taskId": task_id,
                "data": log_entry,
                "timestamp": _now(),
            })

            # Update progress for meaningful lines
            if any(kw in line for kw in ["因子", "回测", "模型", "训练", "完成", "加载",
                                          "[1/4]", "[2/4]", "[3/4]", "[4/4]", "结果"]):
                task["progress"]["message"] = line[:200]

                # Estimate progress from run_backtest step markers
                if "[1/4]" in line:
                    task["progress"]["progress"] = 15
                elif "[2/4]" in line:
                    task["progress"]["progress"] = 35
                elif "[3/4]" in line:
                    task["progress"]["progress"] = 55
                elif "[4/4]" in line:
                    task["progress"]["progress"] = 75
                elif "结果已保存" in line or "回测结果" in line:
                    task["progress"]["progress"] = 95

                task["progress"]["timestamp"] = _now()
                await _broadcast(task_id, {
                    "type": "progress",
                    "taskId": task_id,
                    "data": task["progress"],
                    "timestamp": _now(),
                })

        # --- Process exit ---
        exit_code = await proc.wait()
        task["pid"] = None
        task["status"] = "completed" if exit_code == 0 else "failed"
        task["updatedAt"] = _now()

        # Try to load backtest results from output metrics JSON
        if exit_code == 0:
            task["progress"]["phase"] = "completed"
            task["progress"]["progress"] = 100
            task["progress"]["message"] = "回测完成"
            _load_backtest_results(task)
        else:
            task["progress"]["message"] = f"回测失败 (exit code: {exit_code})"

        await _broadcast(task_id, {
            "type": "result",
            "taskId": task_id,
            "data": {
                "status": task["status"],
                "metrics": task.get("metrics", {}),
            },
            "timestamp": _now(),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        task["status"] = "failed"
        task["progress"]["message"] = str(e)
        task["updatedAt"] = _now()
        await _broadcast(task_id, {
            "type": "error",
            "taskId": task_id,
            "data": {"error": str(e)},
            "timestamp": _now(),
        })
    finally:
        for temporary_path in (temporary_factor_json, temporary_config_path):
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


def _load_backtest_results(task: Dict[str, Any]):
    """Try to load backtest result metrics from the output directory."""
    try:
        config_path = task.get("config", {}).get("configPath") or str(
            PROJECT_ROOT / "configs" / "backtest.yaml"
        )
        with open(config_path, "r") as f:
            bt_config = yaml.safe_load(f)
        output_dir_raw = bt_config.get("experiment", {}).get(
            "output_dir", "data/results/backtest_v2_results"
        )
        # Resolve relative output_dir against PROJECT_ROOT (run_backtest runs with cwd=PROJECT_ROOT)
        output_dir = Path(output_dir_raw)
        if not output_dir.is_absolute():
            output_dir = PROJECT_ROOT / output_dir
        output_dir_str = str(output_dir)

        # Look for most recent metrics JSON
        metrics_files = sorted(
            glob.glob(os.path.join(output_dir_str, "*_backtest_metrics.json")),
            key=os.path.getmtime, reverse=True,
        )
        if metrics_files:
            with open(metrics_files[0], "r") as f:
                metrics_data = json.load(f)
            # The JSON has a nested structure: { metrics: {...}, config: {...}, ... }
            # Flatten: put the inner metrics dict at the top level for the frontend,
            # but also keep meta fields like experiment_name and elapsed_seconds.
            inner_metrics = metrics_data.get("metrics", {})
            flat = {**inner_metrics}
            # Carry over useful metadata
            for key in ("experiment_name", "factor_source", "num_factors",
                        "config", "elapsed_seconds"):
                if key in metrics_data:
                    flat[f"__{key}"] = metrics_data[key]
            
            # Load cumulative excess return data from CSV
            csv_path = metrics_files[0].replace("_backtest_metrics.json", "_cumulative_excess.csv")
            if os.path.exists(csv_path) and "cumulative_curve" not in flat:
                import pandas as pd
                df = pd.read_csv(csv_path)
                if 'date' in df.columns and 'cumulative_excess_return' in df.columns:
                    cumulative_data = df[['date', 'cumulative_excess_return']].to_dict('records')
                    flat["cumulative_curve"] = [
                        {"date": r["date"], "value": r["cumulative_excess_return"]} 
                        for r in cumulative_data
                    ]

            task["metrics"] = flat
    except Exception as e:
        import traceback
        traceback.print_exc()  # print for debugging, but don't crash


# ---- WRDS data endpoints ----

@app.get("/api/v1/wrds/status", response_model=ApiResponse)
async def get_wrds_status():
    from quantaalpha.data.wrds_adapter import inspect_wrds
    dotenv = _load_dotenv_dict()
    wrds_root = dotenv.get("WRDS_ROOT", "/mnt/d/桌面文件/US stock research/wrds")
    try:
        catalog = await asyncio.to_thread(inspect_wrds, wrds_root)
        qlib_dir = Path(dotenv.get("WRDS_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "wrds_sp500")))
        catalog["qlib"] = {
            "path": str(qlib_dir),
            "built": (qlib_dir / "calendars" / "day.txt").exists(),
            "manifest": json.loads((qlib_dir / "wrds_manifest.json").read_text())
                if (qlib_dir / "wrds_manifest.json").exists() else None,
        }
        return ApiResponse(success=True, data=catalog)
    except Exception as error:
        return ApiResponse(success=False, error=str(error))


async def _run_wrds_build(task_id: str, request: WrdsBuildRequest):
    from quantaalpha.data.wrds_adapter import build_sp500_qlib
    task = tasks[task_id]
    try:
        dotenv = _load_dotenv_dict()
        wrds_root = dotenv.get("WRDS_ROOT", "/mnt/d/桌面文件/US stock research/wrds")
        output = dotenv.get("WRDS_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "wrds_sp500"))
        task["progress"]["message"] = "正在从 WRDS 流式构建历史 S&P 500 Qlib 数据..."
        metadata = await asyncio.to_thread(
            build_sp500_qlib, wrds_root, output, PROJECT_ROOT,
            request.startDate, request.endDate,
        )
        task["status"] = "completed"
        task["progress"].update({"progress": 100, "phase": "completed", "message": "WRDS Qlib 数据构建完成"})
        task["result"] = metadata
    except Exception as error:
        task["status"] = "failed"
        task["progress"].update({"phase": "failed", "message": str(error)})
    task["updatedAt"] = _now()


@app.post("/api/v1/wrds/build", response_model=ApiResponse)
async def start_wrds_build(request: WrdsBuildRequest):
    task_id = _gen_id()
    task = {
        "taskId": task_id, "status": "running", "type": "wrds_build",
        "config": request.model_dump(),
        "progress": {"phase": "building", "currentRound": 0, "totalRounds": 1,
                     "progress": 1, "message": "准备 WRDS 数据...", "timestamp": _now()},
        "logs": [], "metrics": {}, "result": None, "pid": None,
        "createdAt": _now(), "updatedAt": _now(),
    }
    tasks[task_id] = task
    asyncio.create_task(_run_wrds_build(task_id, request))
    return ApiResponse(success=True, data={"taskId": task_id, "task": task})


@app.get("/api/v1/wrds/build/{task_id}", response_model=ApiResponse)
async def get_wrds_build(task_id: str):
    task = tasks.get(task_id)
    if task is None or task.get("type") != "wrds_build":
        raise HTTPException(status_code=404, detail="WRDS build task not found")
    return ApiResponse(success=True, data={"task": task})


# ---- China A-share data endpoints ----

@app.get("/api/v1/china/status", response_model=ApiResponse)
async def get_china_status():
    from quantaalpha.data.cn_duckdb_adapter import inspect_cn_duckdb
    dotenv = _load_dotenv_dict()
    db_path = dotenv.get("CN_DUCKDB_PATH", "/mnt/e/A股数据库/AKshare交易/data/market.db")
    try:
        catalog = await asyncio.to_thread(inspect_cn_duckdb, db_path)
        qlib_dir = Path(dotenv.get("CN_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "cn_market")))
        catalog["qlib"] = {
            "path": str(qlib_dir),
            "built": (qlib_dir / "calendars" / "day.txt").exists(),
            "manifest": json.loads((qlib_dir / "cn_market_manifest.json").read_text(encoding="utf-8"))
                if (qlib_dir / "cn_market_manifest.json").exists() else None,
        }
        return ApiResponse(success=True, data=catalog)
    except Exception as error:
        return ApiResponse(success=False, error=str(error))


async def _run_china_build(task_id: str, request: ChinaBuildRequest):
    from quantaalpha.data.cn_duckdb_adapter import build_cn_qlib
    task = tasks[task_id]
    try:
        dotenv = _load_dotenv_dict()
        database = dotenv.get("CN_DUCKDB_PATH", "/mnt/e/A股数据库/AKshare交易/data/market.db")
        output = dotenv.get("CN_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "cn_market"))
        task["progress"]["message"] = "正在按公告日、历史成分和申万行业构建A股日频 Qlib 数据..."
        metadata = await asyncio.to_thread(
            build_cn_qlib, database, output, PROJECT_ROOT, request.startDate, request.endDate,
        )
        task["status"] = "completed"
        task["progress"].update({"progress": 100, "phase": "completed", "message": "A股 Qlib 数据构建完成"})
        task["result"] = metadata
    except Exception as error:
        task["status"] = "failed"
        task["progress"].update({"phase": "failed", "message": str(error)})
    task["updatedAt"] = _now()


@app.post("/api/v1/china/build", response_model=ApiResponse)
async def start_china_build(request: ChinaBuildRequest):
    task_id = _gen_id()
    task = {
        "taskId": task_id, "status": "running", "type": "china_build",
        "config": request.model_dump(),
        "progress": {"phase": "building", "currentRound": 0, "totalRounds": 1,
                     "progress": 1, "message": "准备A股 DuckDB 数据...", "timestamp": _now()},
        "logs": [], "metrics": {}, "result": None, "pid": None,
        "createdAt": _now(), "updatedAt": _now(),
    }
    tasks[task_id] = task
    asyncio.create_task(_run_china_build(task_id, request))
    return ApiResponse(success=True, data={"taskId": task_id, "task": task})


@app.get("/api/v1/china/build/{task_id}", response_model=ApiResponse)
async def get_china_build(task_id: str):
    task = tasks.get(task_id)
    if task is None or task.get("type") != "china_build":
        raise HTTPException(status_code=404, detail="China build task not found")
    return ApiResponse(success=True, data={"task": task})


# ---- Binance USD-M perpetual data endpoints ----

@app.get("/api/v1/crypto/status", response_model=ApiResponse)
async def get_crypto_status():
    from quantaalpha.data.binance_futures_adapter import inspect_binance_qlib
    dotenv = _load_dotenv_dict()
    qlib_path = dotenv.get(
        "CRYPTO_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "binance_usdm")
    )
    try:
        return ApiResponse(success=True, data=inspect_binance_qlib(qlib_path))
    except Exception as error:
        return ApiResponse(success=False, error=str(error))


async def _run_crypto_build(task_id: str, request: CryptoBuildRequest):
    from quantaalpha.data.binance_futures_adapter import build_binance_usdm_qlib
    task = tasks[task_id]
    dotenv = _load_dotenv_dict()
    output = dotenv.get(
        "CRYPTO_QLIB_DATA_DIR", str(PROJECT_ROOT / "data" / "qlib" / "binance_usdm")
    )
    try:
        task["progress"].update({"phase": "download", "message": "正在下载币安 USDT 永续日频数据..."})
        result = await asyncio.to_thread(
            build_binance_usdm_qlib, output, PROJECT_ROOT,
            request.startDate, request.endDate, request.maxSymbols,
        )
        task["status"] = "completed"
        task["result"] = result
        task["progress"].update({"phase": "completed", "progress": 100, "message": "币安永续数据已构建"})
    except Exception as error:
        task["status"] = "failed"
        task["progress"].update({"phase": "failed", "message": str(error)})
    task["updatedAt"] = _now()


@app.post("/api/v1/crypto/build", response_model=ApiResponse)
async def start_crypto_build(request: CryptoBuildRequest):
    task_id = _gen_id()
    task = {
        "taskId": task_id, "status": "running", "type": "crypto_build",
        "config": request.model_dump(),
        "progress": {"phase": "queued", "progress": 0, "message": "准备构建币安 USDT 永续数据"},
        "logs": [], "metrics": {}, "result": None, "pid": None,
        "createdAt": _now(), "updatedAt": _now(),
    }
    tasks[task_id] = task
    asyncio.create_task(_run_crypto_build(task_id, request))
    return ApiResponse(success=True, data={"taskId": task_id, "task": task})


@app.get("/api/v1/crypto/build/{task_id}", response_model=ApiResponse)
async def get_crypto_build(task_id: str):
    task = tasks.get(task_id)
    if task is None or task.get("type") != "crypto_build":
        raise HTTPException(status_code=404, detail="Crypto build task not found")
    return ApiResponse(success=True, data={"task": task})


# ---- System config endpoints ----

@app.get("/api/v1/system/config", response_model=ApiResponse)
async def get_system_config():
    """Read current system configuration from .env and experiment.yaml."""
    dotenv = _load_dotenv_dict()

    # Read experiment.yaml for display
    exp_yaml_path = PROJECT_ROOT / "configs" / "experiment.yaml"
    exp_yaml_content = ""
    if exp_yaml_path.exists():
        exp_yaml_content = exp_yaml_path.read_text(encoding="utf-8")

    # Mask API keys for security
    masked_env = {}
    for k, v in dotenv.items():
        if "KEY" in k.upper() and v:
            masked_env[k] = v[:8] + "..." + v[-4:] if len(v) > 12 else "***"
        else:
            masked_env[k] = v

    return ApiResponse(
        success=True,
        data={
            "env": masked_env,
            "experimentYaml": exp_yaml_content,
            "factorLibraries": [Path(p).name for p in _find_factor_jsons()],
        },
    )


@app.put("/api/v1/system/config", response_model=ApiResponse)
async def update_system_config(update: SystemConfigUpdate):
    """Update .env configuration (non-secret fields only)."""
    if not DOTENV_PATH.exists():
        raise HTTPException(status_code=404, detail=".env file not found")

    content = DOTENV_PATH.read_text(encoding="utf-8")
    updates = {k: v for k, v in update.model_dump().items() if v is not None}

    import re
    import shlex
    for key, val in updates.items():
        # Replace existing line or append
        pattern = rf"^{re.escape(key)}\s*=.*$"
        serialized = str(val).lower() if isinstance(val, bool) else str(val)
        replacement = f"{key}={shlex.quote(serialized)}"
        new_content, n = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if n > 0:
            content = new_content
        else:
            content += f"\n{replacement}\n"

    DOTENV_PATH.write_text(content, encoding="utf-8")
    date_or_market_keys = {
        "MARKET_MODE",
        "DEFAULT_MARKET",
        "TRAIN_START_DATE",
        "TRAIN_END_DATE",
        "VALID_START_DATE",
        "VALID_END_DATE",
        "TEST_START_DATE",
        "TEST_END_DATE",
        "US_TRAIN_START_DATE",
        "US_TRAIN_END_DATE",
        "US_VALID_START_DATE",
        "US_VALID_END_DATE",
        "US_TEST_START_DATE",
        "US_TEST_END_DATE",
        "CN_TRAIN_START_DATE",
        "CN_TRAIN_END_DATE",
        "CN_VALID_START_DATE",
        "CN_VALID_END_DATE",
        "CN_TEST_START_DATE",
        "CN_TEST_END_DATE",
        "CRYPTO_TRAIN_START_DATE",
        "CRYPTO_TRAIN_END_DATE",
        "CRYPTO_VALID_START_DATE",
        "CRYPTO_VALID_END_DATE",
        "CRYPTO_TEST_START_DATE",
        "CRYPTO_TEST_END_DATE",
    }
    cleanup = None
    if date_or_market_keys.intersection(updates):
        cleanup = await asyncio.to_thread(_prune_stale_factor_split_caches)

    return ApiResponse(
        success=True,
        data={"cacheCleanup": cleanup} if cleanup is not None else None,
        message="配置已更新",
    )


# ---- WebSocket endpoint ----

@app.websocket("/ws/mining/{task_id}")
async def ws_mining(websocket: WebSocket, task_id: str):
    """WebSocket for real-time experiment updates."""
    await websocket.accept()

    if task_id not in ws_connections:
        ws_connections[task_id] = []
    ws_connections[task_id].append(websocket)

    # Send current state immediately
    if task_id in tasks:
        try:
            await websocket.send_json({
                "type": "progress",
                "taskId": task_id,
                "data": tasks[task_id].get("progress", {}),
                "timestamp": _now(),
            })
            # Send recent logs
            for log in tasks[task_id].get("logs", [])[-20:]:
                await websocket.send_json({
                    "type": "log",
                    "taskId": task_id,
                    "data": log,
                    "timestamp": _now(),
                })
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            # Heartbeat
            if data == "ping":
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": _now(),
                })
    except WebSocketDisconnect:
        if task_id in ws_connections:
            try:
                ws_connections[task_id].remove(websocket)
            except ValueError:
                pass


# ========================== Entry Point ==========================

def _update_mining_metrics(task: Dict[str, Any]):
    """
    Update mining task metrics from the generated factor library.
    Calculates best factor stats and extracts top 10 factors.
    """
    jsons = _find_factor_jsons()
    # Prefer library with matching suffix if configured
    target_lib = None
    config = task.get("config", {})
    suffix = config.get("librarySuffix")
    
    if suffix:
        candidate = PROJECT_ROOT / "data" / "factorlib" / f"all_factors_library_{suffix}.json"
        # Fix: If suffix is specified, we ONLY look at this file.
        # If it doesn't exist yet, it means no factors have been mined yet for this task.
        if candidate.exists():
            target_lib = str(candidate)
        else:
            # Task specific file not found -> assume empty state
            return
            
    elif jsons:
        # No suffix provided, fallback to latest existing library (legacy behavior)
        target_lib = jsons[0]
        
    if not target_lib:
        return

    # Check modification time
    try:
        mtime = os.path.getmtime(target_lib)
        created_at_str = task.get("createdAt")
        if created_at_str:
            created_at_dt = datetime.fromisoformat(created_at_str)
            # Add a small buffer (e.g. 1 second) to avoid race conditions where file is created immediately
            if mtime < created_at_dt.timestamp():
                # File is older than the task -> ignore it
                return
    except Exception:
        pass

    try:
        lib = _load_factor_library(target_lib)
        factors = lib.get("factors", {})
        
        # 1. Update basic stats
        total = len(factors)
        task["metrics"]["totalFactors"] = total
        
        high = medium = low = 0
        factor_list = []
        
        for f_id, f_info in factors.items():
            # Check if this factor was created after task start
            # If we are using a shared library file (unlikely with new logic, but possible if user forces it),
            # we must ensure we don't display old factors.
            try:
                added_at_str = f_info.get("added_at", "")
                created_at_str = task.get("createdAt", "")
                if added_at_str and created_at_str:
                    # Parse timestamps
                    # added_at usually in isoformat
                    added_at_dt = datetime.fromisoformat(added_at_str)
                    created_at_dt = datetime.fromisoformat(created_at_str)
                    if added_at_dt < created_at_dt:
                        continue
            except Exception:
                pass # If date parsing fails, be permissive or conservative? Permissive for now.

            bt = f_info.get("backtest_results", {})
            quality_assessment = _assess_quality(f_info)
            q = quality_assessment["quality"]
            if q == "high": high += 1
            elif q == "medium": medium += 1
            else: low += 1
            
            # Prepare for top 10 list
            # Normalize metrics
            ic = bt.get("IC", bt.get("1day.excess_return_without_cost.information_coefficient", 0))
            icir = bt.get("ICIR", bt.get("1day.excess_return_without_cost.information_coefficient_ir", 0))
            rank_ic = bt.get("Rank IC", bt.get("rank_ic", bt.get("1day.excess_return_without_cost.rank_ic", 0)))
            rank_icir = bt.get("Rank ICIR", bt.get("rank_ic_ir", bt.get("1day.excess_return_without_cost.rank_ic_ir", 0)))

            preferred_frequencies = config.get("evaluationFrequencies") or []
            frequency = _factor_frequency(bt, preferred_frequencies)
            portfolio_stats = _portfolio_statistics(bt, frequency)
            asset_pricing = _asset_pricing_statistics(bt, frequency)
            industry_statistics = _industry_statistics(bt, frequency)
            factor_market_mode = f_info.get("market_mode") or config.get("marketMode", "us")
            preferred_leg = "long" if factor_market_mode == "cn" else "long_short"
            preferred_portfolio = portfolio_stats.get(preferred_leg, {})

            legacy_annual_return = bt.get("1day.excess_return_without_cost.annualized_return", 0)
            legacy_max_drawdown = bt.get("1day.excess_return_with_cost.max_drawdown",
                                        bt.get("1day.excess_return_without_cost.max_drawdown", 0))
            legacy_sharpe = bt.get("1day.excess_return_with_cost.information_ratio",
                                   bt.get("1day.excess_return_without_cost.information_ratio", 0))
            annual_ret = (preferred_portfolio.get("annualizedNetReturn")
                          if preferred_portfolio.get("annualizedNetReturn") is not None else legacy_annual_return)
            max_dd = (preferred_portfolio.get("maxDrawdown")
                      if preferred_portfolio.get("maxDrawdown") is not None else legacy_max_drawdown)
            sharpe = (preferred_portfolio.get("sharpeRatio")
                      if preferred_portfolio.get("sharpeRatio") is not None else legacy_sharpe)
            cr = annual_ret / abs(max_dd) if max_dd else 0

            factor_list.append({
                "factorName": f_info.get("factor_name", f_id),
                "factorExpression": f_info.get("factor_expression", ""),
                "quality": q,
                "qualityScore": quality_assessment["score"],
                "rankIc": rank_ic,
                "rankIcir": rank_icir,
                "ic": ic,
                "icir": icir,
                "frequency": frequency,
                "portfolioStats": portfolio_stats,
                "preferredPortfolioLeg": preferred_leg,
                "assetPricing": asset_pricing,
                "industryStatistics": industry_statistics,
                "annualReturn": annual_ret,
                "sharpeRatio": sharpe,
                "maxDrawdown": max_dd,
                "calmarRatio": cr,
            })

        task["metrics"]["highQualityFactors"] = high
        task["metrics"]["mediumQualityFactors"] = medium
        task["metrics"]["lowQualityFactors"] = low
        
        # 2. Find best factor
        if factor_list:
            # Sort by comprehensive quality score, then RankIC.
            factor_list.sort(key=lambda x: (x["qualityScore"], abs(x["rankIc"])), reverse=True)
            best = factor_list[0]
            
            # Update task metrics with best factor's stats
            task["metrics"]["annualReturn"] = best["annualReturn"]
            task["metrics"]["rankIc"] = best["rankIc"]
            task["metrics"]["sharpeRatio"] = best["sharpeRatio"]
            task["metrics"]["maxDrawdown"] = best["maxDrawdown"]
            task["metrics"]["factorName"] = best["factorName"]
            
            # 3. Top 10 Factors
            task["metrics"]["top10Factors"] = factor_list[:10]
            
    except Exception:
        pass # Best effort

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    port = int(os.environ.get("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")

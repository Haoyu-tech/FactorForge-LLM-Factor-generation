"""
Factor library manager: save experiment output to unified JSON factor library.
Called from quantaalpha/pipeline/loop.py feedback step.
"""

import json
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_FACTOR_CACHE_DIR = os.environ.get(
    "FACTOR_CACHE_DIR",
    "data/results/factor_cache",
)


def _decode_library_text(text: str) -> dict:
    """Decode one or more complete JSON objects and ignore a torn trailing write."""
    decoder = json.JSONDecoder()
    position = 0
    documents = []
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            break
        try:
            document, end = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            if documents:
                logger.warning("Ignoring incomplete trailing factor-library write at byte %s", position)
                break
            raise
        if isinstance(document, dict):
            documents.append(document)
        position = end
    if not documents:
        raise json.JSONDecodeError("No complete JSON document", text, 0)
    merged = {"metadata": {}, "factors": {}}
    for document in documents:
        if isinstance(document.get("metadata"), dict):
            merged["metadata"].update(document["metadata"])
        if isinstance(document.get("factors"), dict):
            merged["factors"].update(document["factors"])
    return merged


class FactorLibraryManager:
    """Manage unified factor library (CRUD)."""

    def __init__(self, library_path: str):
        self.library_path = Path(library_path)
        self.data = self._load()

    def _load(self) -> dict:
        if self.library_path.exists():
            try:
                return _decode_library_text(self.library_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Factor library file corrupted, recreating: {e}")
        return {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_factors": 0,
                "version": "1.0",
            },
            "factors": {},
        }

    def _save(self):
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.library_path.with_suffix(self.library_path.suffix + ".lock")
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            try:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except ImportError:
                fcntl = None
            try:
                latest = {"metadata": {}, "factors": {}}
                if self.library_path.exists():
                    try:
                        latest = _decode_library_text(self.library_path.read_text(encoding="utf-8"))
                    except Exception as exc:
                        logger.warning("Could not merge current factor library before save: %s", exc)
                latest.setdefault("metadata", {}).update(self.data.get("metadata", {}))
                latest.setdefault("factors", {}).update(self.data.get("factors", {}))
                latest["metadata"]["last_updated"] = datetime.now().isoformat()
                latest["metadata"]["total_factors"] = len(latest["factors"])
                temp_path = self.library_path.with_suffix(
                    self.library_path.suffix + f".tmp.{os.getpid()}"
                )
                temp_path.write_text(
                    json.dumps(latest, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                os.replace(temp_path, self.library_path)
                self.data = latest
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def add_factors_from_experiment(
        self,
        experiment,
        experiment_id: str = "unknown",
        round_number: int = 0,
        hypothesis: Optional[str] = None,
        feedback: Any = None,
        initial_direction: Optional[str] = None,
        user_initial_direction: Optional[str] = None,
        planning_direction: Optional[str] = None,
        evolution_phase: str = "original",
        trajectory_id: str = "",
        parent_trajectory_ids: Optional[list] = None,
    ):
        """Extract factors from a QlibFactorExperiment and write to library."""
        if experiment is None:
            logger.warning("experiment is None, skip saving factors")
            return
        raw_market_mode = os.environ.get("MARKET_MODE", "us").lower()
        market_mode = raw_market_mode if raw_market_mode in {"us", "cn", "crypto"} else "us"
        default_market = {"us": "sp500", "cn": "csi300", "crypto": "binance_usdm"}[market_mode]
        market = os.environ.get("QLIB_MARKET", default_market)
        library_metadata = self.data.setdefault("metadata", {})
        library_metadata["market_mode"] = market_mode
        library_metadata["market"] = market
        library_metadata["scope_label"] = {
            "sp500": "S&P 500",
            "csi300": "沪深300",
            "csi500": "中证500",
            "sme_composite": "中小综指",
            "binance_usdm": "Binance USDT 永续",
        }.get(market, market)
        split_windows = {
            "train": [os.environ.get("TRAIN_START_DATE"), os.environ.get("TRAIN_END_DATE")],
            "valid": [os.environ.get("VALID_START_DATE"), os.environ.get("VALID_END_DATE")],
            "test": [os.environ.get("TEST_START_DATE"), os.environ.get("TEST_END_DATE")],
        }
        library_metadata["split_windows"] = split_windows
        library_metadata["evaluation_frequencies"] = os.environ.get(
            "MINING_EVALUATION_FREQUENCIES", "day,week,month"
        )
        library_metadata["market_filters"] = {
            "exclude_st": os.environ.get("CN_EXCLUDE_ST", "true"),
            "exclude_new_stocks": os.environ.get("CN_EXCLUDE_NEW_STOCKS", "true"),
            "exclude_chinext": os.environ.get("CN_EXCLUDE_CHINEXT", "false"),
            "exclude_star": os.environ.get("CN_EXCLUDE_STAR", "false"),
            "exclude_bse": os.environ.get("CN_EXCLUDE_BSE", "false"),
            "new_stock_min_trading_days": os.environ.get("CN_NEW_STOCK_MIN_TRADING_DAYS", "375"),
        }
        backtest_results = self._extract_backtest_results(experiment)
        feedback_dict = self._extract_feedback(feedback)
        sub_tasks = getattr(experiment, "sub_tasks", []) or []
        sub_workspaces = getattr(experiment, "sub_workspace_list", []) or []

        for idx, task in enumerate(sub_tasks):
            factor_name = getattr(task, "factor_name", getattr(task, "name", f"factor_{idx}"))
            factor_expr = getattr(task, "factor_expression", "")
            factor_desc = getattr(task, "factor_description", getattr(task, "description", ""))
            factor_form = getattr(task, "factor_formulation", "")

            factor_id = hashlib.md5(
                f"{factor_name}_{factor_expr}".encode()
            ).hexdigest()[:16]

            code = ""
            cache_location = {}
            if idx < len(sub_workspaces):
                ws = sub_workspaces[idx]
                code_dict = getattr(ws, "code_dict", {})
                code = "\n".join(
                    f"File: {fname}\n\n{content}"
                    for fname, content in code_dict.items()
                )
                ws_path = getattr(ws, "workspace_path", None)
                if ws_path:
                    ws_path = Path(ws_path)
                    workspace_suffix = ""
                    for part in ws_path.parts:
                        if part.startswith("workspace_"):
                            workspace_suffix = part.replace("workspace_", "")
                            break
                    h5_file = ws_path / "result.h5"
                    cache_location = {
                        "workspace_suffix": workspace_suffix,
                        "workspace_path": str(ws_path.parent),
                        "factor_dir": ws_path.name,
                    }
                    if h5_file.exists():
                        cache_location["result_h5_path"] = str(h5_file)
                    else:
                        logger.warning(
                            f"result.h5 missing for {factor_name} ({h5_file}), will recompute from expression in backtest"
                        )

            factor_metrics = self._factor_backtest_results(backtest_results, factor_name)
            factor_entry = {
                "factor_id": factor_id,
                "market_mode": market_mode,
                "market": market,
                "factor_name": factor_name,
                "factor_expression": factor_expr,
                "factor_implementation_code": code,
                "factor_description": factor_desc,
                "factor_formulation": factor_form,
                "cache_location": cache_location,
                "metadata": {
                    "market_mode": market_mode,
                    "market": market,
                    "split_windows": split_windows,
                    "experiment_id": experiment_id,
                    "round_number": round_number,
                    "evolution_phase": evolution_phase,
                    "trajectory_id": trajectory_id,
                    "parent_trajectory_ids": parent_trajectory_ids or [],
                    "hypothesis": str(hypothesis) if hypothesis else "",
                    "initial_direction": initial_direction or "",
                    "planning_direction": planning_direction or "",
                    "created_at": datetime.now().isoformat(),
                },
                "backtest_results": factor_metrics,
                "statistics_metadata": {
                    "scope": "single_factor",
                    "evaluation_split": getattr(experiment, "evaluation_split", "validation"),
                    "evaluation_window": getattr(
                        experiment, "evaluation_window",
                        [os.environ.get("VALID_START_DATE"), os.environ.get("VALID_END_DATE")],
                    ),
                    "test_policy": "held_out_until_independent_backtest",
                    "metric_count": len(factor_metrics),
                    "updated_at": datetime.now().isoformat(),
                    "schema_version": "2.1",
                },
                "decile_curves": self._factor_decile_curves(experiment, factor_name),
                "llm_explanation": self._factor_llm_explanation(feedback_dict, factor_name),
                "feedback": feedback_dict,
            }

            self.data["factors"][factor_id] = factor_entry

            if factor_expr and cache_location.get("result_h5_path"):
                self._sync_h5_to_md5_cache(factor_expr, cache_location["result_h5_path"])

        self._save()
        logger.info(
            f"Saved {len(sub_tasks)} factors to {self.library_path} (backtest_results: {len(backtest_results)} metrics)"
        )

    @staticmethod
    def _sync_h5_to_md5_cache(factor_expression: str, h5_path: str,
                                cache_dir: Optional[str] = None) -> bool:
        """Sync factor values from result.h5 to MD5 cache dir (.pkl). Returns True on success."""
        cache_dir = Path(cache_dir or DEFAULT_FACTOR_CACHE_DIR)
        h5_file = Path(h5_path)

        if not h5_file.exists():
            return False

        md5_key = hashlib.md5(factor_expression.encode()).hexdigest()
        pkl_file = cache_dir / f"{md5_key}.pkl"

        if pkl_file.exists():
            return True

        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            result = pd.read_hdf(str(h5_file))
            result.to_pickle(pkl_file)
            logger.debug(f"Synced factor cache -> {pkl_file.name}")
            return True
        except Exception as e:
            logger.debug(f"Sync factor cache failed [{h5_path}]: {e}")
            return False

    @staticmethod
    def check_cache_status(library_path: str,
                           cache_dir: Optional[str] = None) -> dict:
        """Check cache status for each factor in library. Returns:
            {
                "total": int,
                "h5_cached": int,
                "md5_cached": int,
                "need_compute": int,
                "factors": [ { "factor_id", "factor_name", "status" }, ... ]
            }
        """
        cache_dir = Path(cache_dir or DEFAULT_FACTOR_CACHE_DIR)

        with open(library_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        factors = data.get("factors", {})
        total = len(factors)
        h5_cached = 0
        md5_cached = 0
        need_compute = 0
        details = []

        for fid, finfo in factors.items():
            expr = finfo.get("factor_expression", "")
            cloc = finfo.get("cache_location", {})
            h5_path = cloc.get("result_h5_path", "")

            status = "need_compute"
            # Check h5 cache
            if h5_path and Path(h5_path).exists():
                status = "h5_cached"
                h5_cached += 1
            # Check MD5 cache
            elif expr:
                md5_key = hashlib.md5(expr.encode()).hexdigest()
                if (cache_dir / f"{md5_key}.pkl").exists():
                    status = "md5_cached"
                    md5_cached += 1

            if status == "need_compute":
                need_compute += 1

            details.append({
                "factor_id": fid,
                "factor_name": finfo.get("factor_name", fid),
                "status": status,
            })

        return {
            "total": total,
            "h5_cached": h5_cached,
            "md5_cached": md5_cached,
            "need_compute": need_compute,
            "factors": details,
        }

    @staticmethod
    def warm_cache_from_json(library_path: str,
                             cache_dir: Optional[str] = None) -> dict:
        """Walk factor library JSON and sync all available result.h5 to MD5 cache dir. Returns:
            { "total": int, "synced": int, "skipped": int, "failed": int,
              "already_cached": int, "no_source": int }
        """
        cache_dir_path = Path(cache_dir or DEFAULT_FACTOR_CACHE_DIR)

        with open(library_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        factors = data.get("factors", {})
        synced = 0
        skipped = 0
        failed = 0
        already_cached = 0
        no_source = 0

        for fid, finfo in factors.items():
            expr = finfo.get("factor_expression", "")
            cloc = finfo.get("cache_location", {})
            h5_path = cloc.get("result_h5_path", "")

            if not expr or not h5_path:
                no_source += 1
                skipped += 1
                continue

            md5_key = hashlib.md5(expr.encode()).hexdigest()
            pkl_file = cache_dir_path / f"{md5_key}.pkl"

            if pkl_file.exists():
                already_cached += 1
                skipped += 1
                continue

            if not Path(h5_path).exists():
                failed += 1
                continue

            try:
                cache_dir_path.mkdir(parents=True, exist_ok=True)
                result = pd.read_hdf(str(h5_path))
                result.to_pickle(pkl_file)
                synced += 1
            except Exception:
                failed += 1

        return {
            "total": len(factors),
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "already_cached": already_cached,
            "no_source": no_source,
        }

    @staticmethod
    def _factor_llm_explanation(feedback: dict, factor_name: str) -> Any:
        explanations = feedback.get("factor_explanations", {}) if isinstance(feedback, dict) else {}
        if not isinstance(explanations, dict):
            return {}
        candidates = (
            str(factor_name),
            str(factor_name).replace(".", "_").replace(" ", "_"),
            str(factor_name).lower(),
        )
        for candidate in candidates:
            if candidate in explanations:
                return explanations[candidate]
        normalized = str(factor_name).replace(".", "_").replace(" ", "_").lower()
        for key, value in explanations.items():
            if str(key).replace(".", "_").replace(" ", "_").lower() == normalized:
                return value
        return {}

    @staticmethod
    def _factor_decile_curves(experiment, factor_name: str, max_points: int = 600) -> dict:
        """Return compact cumulative-return curves for all ten portfolios."""
        safe_name = str(factor_name).replace(".", "_").replace(" ", "_")
        all_factor_analytics = getattr(experiment, "factor_portfolio_analytics", {}) or {}
        analytics = all_factor_analytics.get(safe_name, {})
        output = {}
        for frequency, payload in analytics.items():
            frequency_curves = {}
            for group_name, summary in (payload.get("decile_analytics", {}) or {}).items():
                curve = list(summary.get("curve", []) or [])
                if not curve:
                    continue
                step = max(1, int(np.ceil(len(curve) / max_points)))
                sampled = curve[::step]
                if sampled[-1] != curve[-1]:
                    sampled.append(curve[-1])
                frequency_curves[group_name] = sampled
            if frequency_curves:
                output[frequency] = frequency_curves
        return output

    @staticmethod
    def _factor_backtest_results(results: dict, factor_name: str) -> dict:
        """Extract metrics belonging to one candidate factor.

        Older experiments do not have factor-prefixed metrics, so they retain
        the shared result for backwards compatibility.
        """
        safe_name = str(factor_name).replace(".", "_").replace(" ", "_")
        prefix = f"factor.{safe_name}."
        own = {
            key[len(prefix):]: value
            for key, value in results.items()
            if str(key).startswith(prefix)
        }
        # Modern mining results contain factor-prefixed metrics. Never attach
        # another candidate's statistics when a name mismatch occurs.
        has_scoped_metrics = any(str(key).startswith("factor.") for key in results)
        return own if has_scoped_metrics else results

    @staticmethod
    def _extract_backtest_results(experiment) -> dict:
        """Extract backtest metrics from experiment.result (pandas Series) as dict."""
        result = getattr(experiment, "result", None)
        if result is None:
            return {}
        if isinstance(result, pd.Series):
            out = {}
            for key, val in result.items():
                # NaN/Inf -> None for JSON
                if isinstance(val, (float, np.floating)):
                    if np.isnan(val) or np.isinf(val):
                        out[str(key)] = None
                    else:
                        out[str(key)] = round(float(val), 8)
                else:
                    out[str(key)] = val
            return out

        if isinstance(result, pd.DataFrame):
            try:
                return {
                    str(k): round(float(v), 8) if isinstance(v, (float, np.floating)) and not np.isnan(v) else None
                    for k, v in result.iloc[:, 0].items()
                }
            except Exception:
                pass

        if isinstance(result, dict):
            return result

        return {}

    @staticmethod
    def _extract_feedback(feedback) -> dict:
        """Convert feedback object to serializable dict."""
        if feedback is None:
            return {}
        if isinstance(feedback, dict):
            return feedback

        out = {}
        for attr in ["observations", "hypothesis_evaluation", "decision", "reason",
                      "new_hypothesis", "feedback_str", "factor_explanations"]:
            val = getattr(feedback, attr, None)
            if val is not None:
                out[attr] = val if isinstance(val, (dict, list, bool, int, float)) else str(val)
        if not out:
            out["raw"] = str(feedback)
        return out

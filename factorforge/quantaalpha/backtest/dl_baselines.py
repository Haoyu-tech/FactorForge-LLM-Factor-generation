"""Deep-learning baselines (LSTM, Transformer) scored exactly like mined factors.

The models are Qlib's reference implementations trained on Qlib's Alpha158
feature set over the project's own train / valid / test split.  Their test-set
predictions are then passed through the *same* functions that score every
mined factor (``quantaalpha.backtest.long_short_analytics``), so IC, Rank IC,
ICIR, annualised return and max drawdown are directly comparable.

Run::

    python -m quantaalpha.backtest.dl_baselines --models lstm transformer

Results are written as JSON to ``$DATA_RESULTS_DIR/benchmarks/<market>/<model>.json``
and served by ``GET /api/v1/benchmarks/models``.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Qlib's benchmark configurations (examples/benchmarks/{LSTM,Transformer}/workflow_config_*_Alpha158.yaml).
MODEL_SPECS: Dict[str, Dict[str, Any]] = {
    "lstm": {
        "label": "LSTM",
        "module": "qlib.contrib.model.pytorch_lstm_ts",
        "class": "LSTM",
        "kwargs": {
            "hidden_size": 64, "num_layers": 2, "dropout": 0.0, "n_epochs": 200, "lr": 1e-3,
            "early_stop": 10, "batch_size": 800, "metric": "loss", "loss": "mse", "GPU": 0, "seed": 0,
        },
    },
    "transformer": {
        "label": "Transformer",
        "module": "qlib.contrib.model.pytorch_transformer_ts",
        "class": "TransformerModel",
        "kwargs": {
            "d_model": 64, "nhead": 2, "num_layers": 2, "dropout": 0.0, "n_epochs": 100, "lr": 1e-4,
            "early_stop": 5, "batch_size": 8192, "metric": "loss", "loss": "mse", "reg": 1e-3,
            "GPU": 0, "seed": 0,
        },
    },
}
STEP_LEN = 20
LABEL_EXPRESSION = "Ref($close, -2)/Ref($close, -1) - 1"
INFER_PROCESSORS = [
    {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
    {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
]
LEARN_PROCESSORS = [
    {"class": "DropnaLabel"},
    {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}},
]


def _load_dotenv() -> Dict[str, str]:
    values: Dict[str, str] = {}
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'").strip('"')
    values.update({k: v for k, v in os.environ.items() if k in values or k.endswith("_DATE") or k.endswith("_DIR")})
    return values


def _split_from_env(env: Dict[str, str]) -> Dict[str, List[str]]:
    def pick(key: str, default: str) -> str:
        return env.get(f"US_{key}") or env.get(key) or default
    return {
        "train": [pick("TRAIN_START_DATE", "1987-01-01"), pick("TRAIN_END_DATE", "2010-12-31")],
        "valid": [pick("VALID_START_DATE", "2011-01-01"), pick("VALID_END_DATE", "2014-12-31")],
        "test": [pick("TEST_START_DATE", "2015-01-01"), pick("TEST_END_DATE", "2025-12-31")],
    }


def build_handler(market: str, split: Dict[str, List[str]]):
    """Alpha158 without the VWAP column (the WRDS store has no $vwap field)."""
    from qlib.contrib.data.handler import Alpha158
    from qlib.contrib.data.loader import Alpha158DL

    class Alpha158NoVwap(Alpha158):
        def get_feature_config(self):
            return Alpha158DL.get_feature_config({
                "kbar": {},
                "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW"]},
                "rolling": {},
            })

    return Alpha158NoVwap(
        instruments=market,
        start_time=split["train"][0],
        end_time=split["test"][1],
        fit_start_time=split["train"][0],
        fit_end_time=split["train"][1],
        infer_processors=INFER_PROCESSORS,
        learn_processors=LEARN_PROCESSORS,
        label=([LABEL_EXPRESSION], ["LABEL0"]),
    )


def realized_returns(market: str, split: Dict[str, List[str]]) -> pd.Series:
    """Raw next-day return over the test window, the same label mined factors are scored on."""
    from qlib.data import D

    frame = D.features(D.instruments(market), [LABEL_EXPRESSION],
                       start_time=split["test"][0], end_time=split["test"][1], freq="day")
    series = frame.iloc[:, 0]
    series.index = series.index.set_names(["instrument", "datetime"])
    return series


def _to_float(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return float(value)
    return value


def run_model(name: str, dataset, realized: pd.Series, epochs: int | None, n_jobs: int) -> Dict[str, Any]:
    import importlib
    from quantaalpha.backtest.long_short_analytics import (
        calculate_ic_metrics, calculate_multi_frequency_analytics,
    )

    spec = MODEL_SPECS[name]
    kwargs = dict(spec["kwargs"])
    if epochs is not None:
        kwargs["n_epochs"] = int(epochs)
    kwargs["n_jobs"] = n_jobs
    feature_count = len(dataset.handler.get_cols()) - 1  # last column is the label
    kwargs["d_feat"] = feature_count
    model_cls = getattr(importlib.import_module(spec["module"]), spec["class"])
    model = model_cls(**kwargs)

    evals: Dict[str, list] = {}
    started = time.time()
    model.fit(dataset, evals_result=evals)
    train_seconds = time.time() - started

    pred = model.predict(dataset)  # test segment by default
    pred = pred if isinstance(pred, pd.Series) else pred.iloc[:, 0]
    pred = pred.rename("score")
    long_short_params = {
        "quantile": float(os.environ.get("LONG_SHORT_QUANTILE", "0.1")),
        "min_positions": int(os.environ.get("LONG_SHORT_MIN_POSITIONS", "20")),
        "transaction_cost": float(os.environ.get("LONG_SHORT_TRANSACTION_COST", "0.0005")),
    }
    ic_metrics = calculate_ic_metrics(pred, realized)
    analytics = calculate_multi_frequency_analytics(pred, realized, ("day",), **long_short_params)
    portfolios = analytics["day"]["portfolio_analytics"]
    compact = {
        leg: {k: _to_float(v) for k, v in stats.items() if k not in ("daily_net_returns", "curve")}
        for leg, stats in portfolios.items()
    }
    return {
        "model": name,
        "label": spec["label"],
        "implementation": f"{spec['module']}.{spec['class']}",
        "hyperparameters": {k: _to_float(v) for k, v in kwargs.items()},
        "training": {
            "seconds": round(train_seconds, 1),
            "epochs_run": len(evals.get("train", [])),
            "train_loss": [float(x) for x in evals.get("train", [])],
            "valid_loss": [float(x) for x in evals.get("valid", [])],
        },
        "predictions": {"rows": int(len(pred)), "days": int(pred.index.get_level_values("datetime").nunique())},
        "metrics": {k: float(v) for k, v in ic_metrics.items()},
        "portfolio": compact,
        "preferred_leg": "long_short",
        "long_short_params": long_short_params,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", choices=sorted(MODEL_SPECS), default=["lstm", "transformer"])
    parser.add_argument("--market", default=None, help="Qlib instrument universe (default: DEFAULT_MARKET from .env)")
    parser.add_argument("--provider", default=None, help="Qlib provider dir (default: WRDS_QLIB_DATA_DIR from .env)")
    parser.add_argument("--output", default=None, help="Output dir (default: $DATA_RESULTS_DIR/benchmarks/<market>)")
    parser.add_argument("--epochs", type=int, default=None, help="Override n_epochs (smoke tests only)")
    parser.add_argument("--train-start", default=None, help="Override train start date (smoke tests only)")
    parser.add_argument("--n-jobs", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    args = parser.parse_args(argv)

    env = _load_dotenv()
    market = args.market or env.get("DEFAULT_MARKET", "sp500")
    provider = args.provider or env.get("WRDS_QLIB_DATA_DIR") or str(PROJECT_ROOT / "data" / "qlib" / "wrds_sp500")
    provider = str(Path(provider).expanduser())
    results_dir = Path(env.get("DATA_RESULTS_DIR", "./data/results"))
    if not results_dir.is_absolute():
        results_dir = PROJECT_ROOT / results_dir
    output = Path(args.output) if args.output else results_dir / "benchmarks" / market
    output.mkdir(parents=True, exist_ok=True)
    split = _split_from_env(env)
    if args.train_start:
        split["train"][0] = args.train_start

    try:
        import torch  # noqa: F401
    except ImportError:
        print("PyTorch is not installed in this environment; install it before running baselines.", file=sys.stderr)
        return 2

    import qlib
    from qlib.constant import REG_US
    from qlib.data.dataset import TSDatasetH

    qlib.init(provider_uri=provider, region=REG_US)
    print(f"[1/3] Building Alpha158 features for {market} from {provider}", flush=True)
    handler = build_handler(market, split)
    dataset = TSDatasetH(handler=handler, segments={k: tuple(v) for k, v in split.items()}, step_len=STEP_LEN)
    realized = realized_returns(market, split)
    feature_count = len(handler.get_cols()) - 1
    print(f"      {feature_count} features, step_len={STEP_LEN}, split={split}", flush=True)

    for index, name in enumerate(args.models, start=1):
        print(f"[2/3] Training {MODEL_SPECS[name]['label']} ({index}/{len(args.models)})", flush=True)
        result = run_model(name, dataset, realized, args.epochs, args.n_jobs)
        result.update({
            "market": market,
            "provider_uri": provider,
            "split": split,
            "label_expression": LABEL_EXPRESSION,
            "features": {
                "handler": "qlib.contrib.data.handler.Alpha158 (VWAP column removed)",
                "count": feature_count,
                "step_len": STEP_LEN,
                "infer_processors": INFER_PROCESSORS,
                "learn_processors": LEARN_PROCESSORS,
            },
            "scoring": "quantaalpha.backtest.long_short_analytics (same functions as mined factors)",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "host": platform.node(),
            "smoke_run": bool(args.epochs is not None or args.train_start),
        })
        target = output / f"{name}.json"
        target.write_text(json.dumps(result, indent=2), encoding="utf-8")
        m, ls = result["metrics"], result["portfolio"].get("long_short", {})
        print(f"[3/3] {MODEL_SPECS[name]['label']}: IC={m['IC']:.4f} RankIC={m['Rank IC']:.4f} ICIR={m['ICIR']:.3f} "
              f"AR={ls.get('annualized_net_return', float('nan')):.2%} MDD={ls.get('max_drawdown', float('nan')):.2%} "
              f"-> {target}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

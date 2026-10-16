"""
QuantaAlpha custom workspace.

Overrides rdagent QlibFBWorkspace: project-level factor_template overrides default YAML;
base files (read_exp_res.py, etc.) still from rdagent; init empty git repo in workspace to suppress qlib recorder git output.
"""

import os
import subprocess
from pathlib import Path

import yaml

from quantaalpha.backtest.calendar_guard import clamp_backtest_end_date

from rdagent.scenarios.qlib.experiment.workspace import QlibFBWorkspace as _RdagentQlibFBWorkspace
from rdagent.log import rdagent_logger as logger

_CUSTOM_TEMPLATE_DIR = Path(__file__).resolve().parent / "factor_template"


class QlibFBWorkspace(_RdagentQlibFBWorkspace):
    """
    Override rdagent QlibFBWorkspace: inject project factor_template/ YAML over defaults;
    init empty git repo in workspace to avoid qlib recorder git help output.
    """

    def __init__(self, template_folder_path: Path, *args, **kwargs) -> None:
        super().__init__(template_folder_path, *args, **kwargs)
        if _CUSTOM_TEMPLATE_DIR.exists():
            self.inject_code_from_folder(_CUSTOM_TEMPLATE_DIR)
            logger.info(f"Overrode rdagent default config with project template: {_CUSTOM_TEMPLATE_DIR}")

    def before_execute(self) -> None:
        """Prepare workspace and keep a settlement day after the backtest window."""
        super().before_execute()
        for config_name in ("conf_baseline.yaml", "conf_combined_factors.yaml"):
            config_path = self.workspace_path / config_name
            if not config_path.exists():
                continue
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

            provider_uri = os.environ.get("QLIB_DATA_DIR")
            if provider_uri:
                config.setdefault("qlib_init", {})["provider_uri"] = provider_uri

            segment_env = {
                "train": ("TRAIN_START_DATE", "TRAIN_END_DATE"),
                "valid": ("VALID_START_DATE", "VALID_END_DATE"),
                "test": ("TEST_START_DATE", "TEST_END_DATE"),
            }
            segments = (
                config.setdefault("task", {})
                .setdefault("dataset", {})
                .setdefault("kwargs", {})
                .setdefault("segments", {})
            )
            for segment, (start_key, end_key) in segment_env.items():
                start = os.environ.get(start_key)
                end = os.environ.get(end_key)
                if start and end:
                    segments[segment] = [start, end]

            # Qlib writes predictions from the segment named "test". During
            # mining, map that output segment to validation so the true test
            # period cannot enter model or portfolio analytics.
            evaluation_split = os.environ.get(
                "MINING_EVALUATION_SPLIT", "valid"
            ).strip().lower()
            if evaluation_split not in {"valid", "test"}:
                evaluation_split = "valid"
            evaluation_segment = segments.get(evaluation_split)
            if isinstance(evaluation_segment, list) and len(evaluation_segment) == 2:
                segments["test"] = list(evaluation_segment)
                logger.info(
                    f"Mining evaluation split: {evaluation_split} "
                    f"{evaluation_segment[0]} to {evaluation_segment[1]}"
                )

            handler = (
                config.setdefault("task", {})
                .setdefault("dataset", {})
                .setdefault("kwargs", {})
                .setdefault("handler", {})
                .setdefault("kwargs", {})
            )
            configured_segments = [value for value in segments.values() if isinstance(value, list) and len(value) == 2]
            if configured_segments:
                handler["start_time"] = min(value[0] for value in configured_segments)
                handler["end_time"] = max(value[1] for value in configured_segments)

            test_segment = segments.get("test")
            if isinstance(test_segment, list) and len(test_segment) == 2:
                port_backtest = config.setdefault("port_analysis_config", {}).setdefault("backtest", {})
                port_backtest["start_time"] = test_segment[0]
                port_backtest["end_time"] = test_segment[1]

            safe_end = clamp_backtest_end_date(config)
            if safe_end:
                config_path.write_text(
                    yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                logger.info(f"Adjusted portfolio backtest end to {safe_end} to preserve Qlib calendar lookahead")

        git_dir = self.workspace_path / ".git"
        if not git_dir.exists():
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=str(self.workspace_path),
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass

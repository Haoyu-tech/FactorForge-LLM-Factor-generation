from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from quantaalpha.log import logger
from quantaalpha.llm.client import APIBackend


def _load_prompts(prompt_file: Path) -> dict[str, str]:
    if not prompt_file.exists():
        return {}
    try:
        return yaml.safe_load(prompt_file.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning(f"Failed to load planning prompts: {exc}")
        return {}


def _extract_json(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    fence = re.search(r"```json\s*(.*?)```", t, re.DOTALL | re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start : end + 1]
    return t


def _parse_directions(message: str, n: int) -> list[str] | None:
    frag = _extract_json(message)
    try:
        data = json.loads(frag)
    except Exception:
        return None
    arr = data.get("directions") if isinstance(data, dict) else None
    if not isinstance(arr, list):
        return None
    vals = [str(x).strip() for x in arr if isinstance(x, str) and x.strip()]
    return vals if len(vals) >= n else None


def _fallback_directions(initial_direction: str, n: int) -> list[str]:
    base = initial_direction.strip() if initial_direction else "market microstructure"
    patterns = [
        f"{base} + short-term momentum signal with volume confirmation",
        f"{base} + volatility regime switch using rolling variance",
        f"{base} + liquidity/turnover adjustment for noise reduction",
        f"{base} + cross-sectional rank with sector-neutralization",
        f"{base} + open-to-close versus close-to-open return decomposition",
        f"{base} + calendar effects and seasonality-aware normalization",
        f"{base} + risk-adjusted return features (downside volatility focus)",
    ]
    if os.environ.get("MARKET_MODE", "us").strip().lower() != "crypto":
        # Equity stores carry point-in-time fundamentals; crypto stores do not.
        patterns.insert(5, f"{base} + alignment with stored point-in-time fundamentals")
    out = []
    for i in range(n):
        out.append(patterns[i % len(patterns)])
    return out


def _stored_field_catalog() -> str:
    """Describe the fields in the Qlib store this run reads (QLIB_DATA_DIR)."""
    try:
        from quantaalpha.research.data_feasibility import field_catalog_text, store_fields

        return field_catalog_text(store_fields(os.environ.get("QLIB_DATA_DIR")))
    except Exception as exc:
        logger.warning(f"Could not list stored fields for planning: {exc}")
        return ""


def generate_parallel_directions(
    initial_direction: str,
    n: int,
    prompt_file: Path,
    max_attempts: int = 5,
    use_llm: bool = True,
    allow_fallback: bool = True,
    data_catalog: str | None = None,
) -> list[str]:
    n = max(1, int(n))
    prompts = _load_prompts(prompt_file)
    sys_tpl = prompts.get("system", "")
    user_tpl = prompts.get("user", "")
    output_format = prompts.get("output_format", "")

    system_prompt = sys_tpl.format(initial_direction=initial_direction, n=n)
    user_prompt = user_tpl.format(initial_direction=initial_direction, n=n)
    catalog = data_catalog if data_catalog is not None else _stored_field_catalog()
    if catalog:
        # Without the field list the planner proposes directions that need data
        # the store lacks, and later steps fill the gap with stand-ins.
        user_prompt += (
            "\n\nThe database holds ONLY these daily fields:\n" + catalog
            + "\nEvery direction must be testable with these fields alone. Do not propose directions "
            "that need other data (analyst forecasts, options, news, intraday, on-chain, ...), and do "
            "not relabel a price or volume pattern as such data."
        )
    if output_format:
        if "{n}" in output_format:
            output_format = output_format.replace("{n}", str(n))
        user_prompt = f"{user_prompt}\n\n{output_format}"

    if not use_llm:
        return _fallback_directions(initial_direction, n) if allow_fallback else []

    for attempt in range(1, max_attempts + 1):
        try:
            resp = APIBackend().build_messages_and_create_chat_completion(
                user_prompt=user_prompt, system_prompt=system_prompt, json_mode=False
            )
            directions = _parse_directions(resp, n)
            if directions:
                return directions[:n]
            system_prompt += "\n\nStrictly output valid JSON. No extra text."
            logger.warning(f"Planning parse failed (attempt {attempt}), retrying...")
        except Exception as exc:
            logger.warning(f"Planning LLM call failed (attempt {attempt}): {exc}")

    return _fallback_directions(initial_direction, n) if allow_fallback else []


def load_run_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning(f"Failed to load run config: {exc}")
        return {}


from __future__ import annotations

import hashlib
import inspect
import json
import os
import random
import re
import shutil
import sqlite3
import ssl
import subprocess
import time
import urllib.request
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

import numpy as np
import tiktoken

from quantaalpha.core.utils import LLM_CACHE_SEED_GEN, SingletonBaseClass
from quantaalpha.log import LogColors, logger
from quantaalpha.log import logger
from quantaalpha.llm.config import LLM_SETTINGS

DEFAULT_QLIB_DOT_PATH = Path("./")


def md5_hash(input_string: str) -> str:
    hash_md5 = hashlib.md5(usedforsecurity=False)
    input_bytes = input_string.encode("utf-8")
    hash_md5.update(input_bytes)
    return hash_md5.hexdigest()


def robust_json_parse(text: str, max_retries: int = 3) -> dict:
    """
    Robust JSON parser: handles extra data, LaTeX escapes, markdown-wrapped JSON.
    Raises json.JSONDecodeError if all strategies fail.
    """
    original_text = text

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: extract JSON code block
    json_block_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
    matches = re.findall(json_block_pattern, text)
    if matches:
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # Strategy 3: find first complete JSON object (extra data)
    brace_count = 0
    start_idx = -1
    end_idx = -1
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
            
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                end_idx = i
                break
    
    if start_idx != -1 and end_idx != -1:
        json_str = text[start_idx:end_idx + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Strategy 4: fix LaTeX escapes
            fixed_str = json_str
            latex_commands = ['text', 'frac', 'left', 'right', 'times', 'cdot', 'sqrt', 
                              'sum', 'prod', 'int', 'alpha', 'beta', 'gamma', 'delta']
            for cmd in latex_commands:
                fixed_str = re.sub(r'(?<!\\)\\(' + cmd + r')', r'\\\\\1', fixed_str)
            fixed_str = re.sub(r'(?<!\\)\\([_\{\}\[\]])', r'\\\\\1', fixed_str)
            
            try:
                return json.loads(fixed_str)
            except json.JSONDecodeError:
                pass
    
    # Strategy 5: repair common non-standard escapes emitted by local/gateway
    # models (for example \$ and \_), plus literal control characters in strings.
    # These are frequent in factor names and expressions and are invalid in strict JSON.
    if start_idx != -1 and end_idx != -1:
        candidate = text[start_idx:end_idx + 1]
        candidate = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', candidate)

        repaired_chars: list[str] = []
        in_repaired_string = False
        repaired_escape = False
        for char in candidate:
            if repaired_escape:
                repaired_chars.append(char)
                repaired_escape = False
                continue
            if char == '\\' and in_repaired_string:
                repaired_chars.append(char)
                repaired_escape = True
                continue
            if char == '"':
                in_repaired_string = not in_repaired_string
                repaired_chars.append(char)
                continue
            if in_repaired_string and char in {'\n', '\r', '\t'}:
                repaired_chars.append({'\n': r'\n', '\r': r'\r', '\t': r'\t'}[char])
            else:
                repaired_chars.append(char)

        repaired_json = ''.join(repaired_chars)
        repaired_json = re.sub(r',\s*([}\]])', r'\1', repaired_json)
        try:
            return json.loads(repaired_json)
        except json.JSONDecodeError:
            pass

    # Strategy 6: looser JSON extraction
    potential_jsons = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    for pj in potential_jsons:
        try:
            result = json.loads(pj)
            if isinstance(result, dict) and len(result) > 0:
                return result
        except json.JSONDecodeError:
            continue
    
    raise json.JSONDecodeError(
        f"Could not parse JSON; original text length: {len(original_text)}",
        original_text,
        0,
    )


try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
except ImportError:
    logger.warning("azure.identity is not installed.")

try:
    import openai
except ImportError:
    logger.warning("openai is not installed.")

try:
    from llama import Llama
except ImportError:
    Llama = None  # type: ignore[misc, assignment]


class ConvManager:
    """
    This is a conversation manager of LLM
    It is for convenience of exporting conversation for debugging.
    """

    def __init__(
        self,
        path: Path | str = DEFAULT_QLIB_DOT_PATH / "llm_conv",
        recent_n: int = 10,
    ) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.recent_n = recent_n

    def _rotate_files(self) -> None:
        pairs = []
        for f in self.path.glob("*.json"):
            m = re.match(r"(\d+).json", f.name)
            if m is not None:
                n = int(m.group(1))
                pairs.append((n, f))
        pairs.sort(key=lambda x: x[0])
        for n, f in pairs[: self.recent_n][::-1]:
            if (self.path / f"{n+1}.json").exists():
                (self.path / f"{n+1}.json").unlink()
            f.rename(self.path / f"{n+1}.json")

    def append(self, conv: tuple[list, str]) -> None:
        self._rotate_files()
        with (self.path / "0.json").open("w") as file:
            json.dump(conv, file)
        # TODO: reseve line breaks to make it more convient to edit file directly.


class SQliteLazyCache(SingletonBaseClass):
    def __init__(self, cache_location: str) -> None:
        super().__init__()
        self.cache_location = cache_location
        db_file_exist = Path(cache_location).exists()
        # TODO: sqlite3 does not support multiprocessing.
        self.conn = sqlite3.connect(cache_location, timeout=20)
        self.c = self.conn.cursor()
        if not db_file_exist:
            self.c.execute(
                """
                CREATE TABLE chat_cache (
                    md5_key TEXT PRIMARY KEY,
                    chat TEXT
                )
                """,
            )
            self.c.execute(
                """
                CREATE TABLE embedding_cache (
                    md5_key TEXT PRIMARY KEY,
                    embedding TEXT
                )
                """,
            )
            self.c.execute(
                """
                CREATE TABLE message_cache (
                    conversation_id TEXT PRIMARY KEY,
                    message TEXT
                )
                """,
            )
            self.conn.commit()

    def chat_get(self, key: str) -> str | None:
        md5_key = md5_hash(key)
        self.c.execute("SELECT chat FROM chat_cache WHERE md5_key=?", (md5_key,))
        result = self.c.fetchone()
        if result is None:
            return None
        return result[0]

    def embedding_get(self, key: str) -> list | dict | str | None:
        md5_key = md5_hash(key)
        self.c.execute("SELECT embedding FROM embedding_cache WHERE md5_key=?", (md5_key,))
        result = self.c.fetchone()
        if result is None:
            return None
        return json.loads(result[0])

    def chat_set(self, key: str, value: str) -> None:
        md5_key = md5_hash(key)
        self.c.execute(
            "INSERT OR REPLACE INTO chat_cache (md5_key, chat) VALUES (?, ?)",
            (md5_key, value),
        )
        self.conn.commit()

    def embedding_set(self, content_to_embedding_dict: dict) -> None:
        for key, value in content_to_embedding_dict.items():
            md5_key = md5_hash(key)
            self.c.execute(
                "INSERT OR REPLACE INTO embedding_cache (md5_key, embedding) VALUES (?, ?)",
                (md5_key, json.dumps(value)),
            )
        self.conn.commit()

    def message_get(self, conversation_id: str) -> list[str]:
        self.c.execute("SELECT message FROM message_cache WHERE conversation_id=?", (conversation_id,))
        result = self.c.fetchone()
        if result is None:
            return []
        return json.loads(result[0])

    def message_set(self, conversation_id: str, message_value: list[str]) -> None:
        self.c.execute(
            "INSERT OR REPLACE INTO message_cache (conversation_id, message) VALUES (?, ?)",
            (conversation_id, json.dumps(message_value)),
        )
        self.conn.commit()


class SessionChatHistoryCache(SingletonBaseClass):
    def __init__(self) -> None:
        """load all history conversation json file from self.session_cache_location"""
        self.cache = SQliteLazyCache(cache_location=LLM_SETTINGS.prompt_cache_path)

    def message_get(self, conversation_id: str) -> list[str]:
        return self.cache.message_get(conversation_id)

    def message_set(self, conversation_id: str, message_value: list[str]) -> None:
        self.cache.message_set(conversation_id, message_value)


class ChatSession:
    def __init__(self, api_backend: Any, conversation_id: str | None = None, system_prompt: str | None = None) -> None:
        self.conversation_id = str(uuid.uuid4()) if conversation_id is None else conversation_id
        self.system_prompt = system_prompt if system_prompt is not None else LLM_SETTINGS.default_system_prompt
        self.api_backend = api_backend

    def build_chat_completion_message(self, user_prompt: str) -> list[dict[str, Any]]:
        history_message = SessionChatHistoryCache().message_get(self.conversation_id)
        messages = history_message
        if not messages:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            },
        )
        return messages

    def build_chat_completion_message_and_calculate_token(self, user_prompt: str) -> Any:
        messages = self.build_chat_completion_message(user_prompt)
        return self.api_backend.calculate_token_from_messages(messages)

    def build_chat_completion(self, user_prompt: str, **kwargs: Any) -> str:
        """
        this function is to build the session messages
        user prompt should always be provided
        """
        messages = self.build_chat_completion_message(user_prompt)

        with logger.tag(f"session_{self.conversation_id}"):
            response = self.api_backend._try_create_chat_completion_or_embedding(  # noqa: SLF001
                messages=messages,
                chat_completion=True,
                **kwargs,
            )

        messages.append(
            {
                "role": "assistant",
                "content": response,
            },
        )
        SessionChatHistoryCache().message_set(self.conversation_id, messages)
        return response

    def get_conversation_id(self) -> str:
        return self.conversation_id

    def display_history(self) -> None:
        # TODO: Realize a beautiful presentation format for history messages
        pass


class APIBackend:
    """
    This is a unified interface for different backends.

    (xiao) thinks integrate all kinds of API in a single class is not a good design.
    So we should split them into different classes in `oai/backends/` in the future.
    """

    # FIXME: (xiao) We should avoid using self.xxxx.
    # Instead, we can use LLM_SETTINGS directly. If it's difficult to support different backend settings, we can split them into multiple BaseSettings.
    def __init__(  # noqa: C901, PLR0912, PLR0915
        self,
        *,
        chat_api_key: str | None = None,
        chat_model: str | None = None,
        reasoning_model: str | None = None,
        chat_api_base: str | None = None,
        chat_api_version: str | None = None,
        embedding_api_key: str | None = None,
        embedding_model: str | None = None,
        embedding_api_base: str | None = None,
        embedding_api_version: str | None = None,
        use_chat_cache: bool | None = None,
        dump_chat_cache: bool | None = None,
        use_embedding_cache: bool | None = None,
        dump_embedding_cache: bool | None = None,
    ) -> None:
        self.use_codex_cli = LLM_SETTINGS.use_codex_cli
        self.use_claude_cli = LLM_SETTINGS.use_claude_cli
        if LLM_SETTINGS.use_llama2:
            if Llama is None:
                raise RuntimeError("USE_LLAMA2=True requires the optional llama package to be installed.")
            self.generator = Llama.build(
                ckpt_dir=LLM_SETTINGS.llama2_ckpt_dir,
                tokenizer_path=LLM_SETTINGS.llama2_tokenizer_path,
                max_seq_len=LLM_SETTINGS.max_tokens,
                max_batch_size=LLM_SETTINGS.llams2_max_batch_size,
            )
            self.encoder = None
        elif LLM_SETTINGS.use_gcr_endpoint:
            gcr_endpoint_type = LLM_SETTINGS.gcr_endpoint_type
            if gcr_endpoint_type == "llama2_70b":
                self.gcr_endpoint_key = LLM_SETTINGS.llama2_70b_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.llama2_70b_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.llama2_70b_endpoint
            elif gcr_endpoint_type == "llama3_70b":
                self.gcr_endpoint_key = LLM_SETTINGS.llama3_70b_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.llama3_70b_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.llama3_70b_endpoint
            elif gcr_endpoint_type == "phi2":
                self.gcr_endpoint_key = LLM_SETTINGS.phi2_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.phi2_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.phi2_endpoint
            elif gcr_endpoint_type == "phi3_4k":
                self.gcr_endpoint_key = LLM_SETTINGS.phi3_4k_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.phi3_4k_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.phi3_4k_endpoint
            elif gcr_endpoint_type == "phi3_128k":
                self.gcr_endpoint_key = LLM_SETTINGS.phi3_128k_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.phi3_128k_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.phi3_128k_endpoint
            else:
                error_message = f"Invalid gcr_endpoint_type: {gcr_endpoint_type}"
                raise ValueError(error_message)
            self.headers = {
                "Content-Type": "application/json",
                "Authorization": ("Bearer " + self.gcr_endpoint_key),
            }
            self.gcr_endpoint_temperature = LLM_SETTINGS.gcr_endpoint_temperature
            self.gcr_endpoint_top_p = LLM_SETTINGS.gcr_endpoint_top_p
            self.gcr_endpoint_do_sample = LLM_SETTINGS.gcr_endpoint_do_sample
            self.gcr_endpoint_max_token = LLM_SETTINGS.gcr_endpoint_max_token
            if not os.environ.get("PYTHONHTTPSVERIFY", "") and hasattr(ssl, "_create_unverified_context"):
                ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
            self.chat_model_map = json.loads(LLM_SETTINGS.chat_model_map)
            self.chat_model = LLM_SETTINGS.chat_model if chat_model is None else chat_model
            self.encoder = None
        else:
            self.use_azure = LLM_SETTINGS.use_azure
            self.chat_use_azure_token_provider = LLM_SETTINGS.chat_use_azure_token_provider
            self.embedding_use_azure_token_provider = LLM_SETTINGS.embedding_use_azure_token_provider
            self.managed_identity_client_id = LLM_SETTINGS.managed_identity_client_id

            # Priority: chat_api_key/embedding_api_key > openai_api_key > os.environ.get("OPENAI_API_KEY")
            # TODO: Simplify the key design. Consider Pandatic's field alias & priority.
            self.chat_api_key = (
                chat_api_key
                or LLM_SETTINGS.chat_openai_api_key
                or LLM_SETTINGS.openai_api_key
                or os.environ.get("OPENAI_API_KEY")
            )
            self.embedding_api_key = (
                embedding_api_key
                or LLM_SETTINGS.embedding_openai_api_key
                or LLM_SETTINGS.openai_api_key
                or os.environ.get("OPENAI_API_KEY")
            )
            
            self.base_url = (
                LLM_SETTINGS.openai_base_url
                or os.environ.get("OPENAI_BASE_URL")
            )
            
            self.embedding_base_url = (
                LLM_SETTINGS.embedding_base_url
                or os.environ.get("EMBEDDING_BASE_URL")
            )

            self.embedding_api_key = (
                LLM_SETTINGS.embedding_api_key
                or os.environ.get("EMBEDDING_API_KEY")
            )
            

            self.chat_model = LLM_SETTINGS.chat_model if chat_model is None else chat_model
            self.reasoning_model = LLM_SETTINGS.reasoning_model if reasoning_model is None else reasoning_model
            self.chat_model_map = json.loads(LLM_SETTINGS.chat_model_map)
            # self.encoder = self._get_encoder()
            
            self.chat_api_base = LLM_SETTINGS.chat_azure_api_base if chat_api_base is None else chat_api_base
            self.chat_api_version = (
                LLM_SETTINGS.chat_azure_api_version if chat_api_version is None else chat_api_version
            )
            self.chat_stream = LLM_SETTINGS.chat_stream
            self.chat_seed = LLM_SETTINGS.chat_seed

            self.embedding_model = LLM_SETTINGS.embedding_model if embedding_model is None else embedding_model
            self.embedding_api_base = (
                LLM_SETTINGS.embedding_azure_api_base if embedding_api_base is None else embedding_api_base
            )
            self.embedding_api_version = (
                LLM_SETTINGS.embedding_azure_api_version if embedding_api_version is None else embedding_api_version
            )

            if self.use_azure:
                if self.chat_use_azure_token_provider or self.embedding_use_azure_token_provider:
                    dac_kwargs = {}
                    if self.managed_identity_client_id is not None:
                        dac_kwargs["managed_identity_client_id"] = self.managed_identity_client_id
                    credential = DefaultAzureCredential(**dac_kwargs)
                    token_provider = get_bearer_token_provider(
                        credential,
                        "https://cognitiveservices.azure.com/.default",
                    )
                if self.chat_use_azure_token_provider:
                    self.chat_client = openai.AzureOpenAI(
                        azure_ad_token_provider=token_provider,
                        timeout=LLM_SETTINGS.chat_request_timeout_seconds,
                        max_retries=LLM_SETTINGS.chat_sdk_max_retries,
                        api_version=self.chat_api_version,
                        azure_endpoint=self.chat_api_base,
                    )
                else:
                    self.chat_client = openai.AzureOpenAI(
                        api_key=self.chat_api_key,
                        timeout=LLM_SETTINGS.chat_request_timeout_seconds,
                        max_retries=LLM_SETTINGS.chat_sdk_max_retries,
                        api_version=self.chat_api_version,
                        azure_endpoint=self.chat_api_base,
                    )

                if self.embedding_use_azure_token_provider:
                    self.embedding_client = openai.AzureOpenAI(
                        azure_ad_token_provider=token_provider,
                        api_version=self.embedding_api_version,
                        azure_endpoint=self.embedding_api_base,
                    )
                else:
                    self.embedding_client = openai.AzureOpenAI(
                        api_key=self.embedding_api_key,
                        api_version=self.embedding_api_version,
                        azure_endpoint=self.embedding_api_base,
                    )
            elif self.use_codex_cli or self.use_claude_cli:
                # Chat requests go through a locally authenticated CLI.
                # Embeddings are still optional and use the HTTP API when they
                # have been configured explicitly.
                self.chat_client = None
                self.embedding_client = (
                    openai.OpenAI(api_key=self.embedding_api_key, base_url=self.embedding_base_url or None)
                    if self.embedding_api_key and self.embedding_model
                    else None
                )
            else:
                self.chat_client = openai.OpenAI(
                    api_key=self.chat_api_key,
                    base_url=self.base_url,
                    timeout=LLM_SETTINGS.chat_request_timeout_seconds,
                    max_retries=LLM_SETTINGS.chat_sdk_max_retries,
                )
                self.embedding_client = (
                    openai.OpenAI(api_key=self.embedding_api_key, base_url=self.embedding_base_url or None)
                    if self.embedding_api_key and self.embedding_model
                    else None
                )

        self.dump_chat_cache = LLM_SETTINGS.dump_chat_cache if dump_chat_cache is None else dump_chat_cache
        self.use_chat_cache = LLM_SETTINGS.use_chat_cache if use_chat_cache is None else use_chat_cache
        self.dump_embedding_cache = (
            LLM_SETTINGS.dump_embedding_cache if dump_embedding_cache is None else dump_embedding_cache
        )
        self.use_embedding_cache = (
            LLM_SETTINGS.use_embedding_cache if use_embedding_cache is None else use_embedding_cache
        )
        if self.dump_chat_cache or self.use_chat_cache or self.dump_embedding_cache or self.use_embedding_cache:
            self.cache_file_location = LLM_SETTINGS.prompt_cache_path
            self.cache = SQliteLazyCache(cache_location=self.cache_file_location)

        # transfer the config to the class if the config is not supposed to change during the runtime
        self.use_llama2 = LLM_SETTINGS.use_llama2
        self.use_gcr_endpoint = LLM_SETTINGS.use_gcr_endpoint
        self.retry_wait_seconds = LLM_SETTINGS.retry_wait_seconds

    def _get_encoder(self):
        """
        tiktoken.encoding_for_model(self.chat_model) does not cover all cases it should consider.

        This function attempts to handle several edge cases.
        """

        # 1) cases
        def _azure_patch(model: str) -> str:
            """
            When using Azure API, self.chat_model is the deployment name that can be any string.
            For example, it may be `gpt-4o_2024-08-06`. But tiktoken.encoding_for_model can't handle this.
            """
            return model.replace("_", "-")

        model = self.chat_model
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Failed to get encoder. Trying to patch the model name")
            for patch_func in [_azure_patch]:
                try:
                    return tiktoken.encoding_for_model(patch_func(model))
                except KeyError:
                    logger.error(f"Failed to get encoder even after patching with {patch_func.__name__}")
                    raise

    def build_chat_session(
        self,
        conversation_id: str | None = None,
        session_system_prompt: str | None = None,
    ) -> ChatSession:
        """
        conversation_id is a 256-bit string created by uuid.uuid4() and is also
        the file name under session_cache_folder/ for each conversation
        """
        return ChatSession(self, conversation_id, session_system_prompt)

    def build_messages(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        former_messages: list[dict] | None = None,
        *,
        shrink_multiple_break: bool = False,
    ) -> list[dict]:
        """
        build the messages to avoid implementing several redundant lines of code

        """
        if former_messages is None:
            former_messages = []
        # shrink multiple break will recursively remove multiple breaks(more than 2)
        if shrink_multiple_break:
            while "\n\n\n" in user_prompt:
                user_prompt = user_prompt.replace("\n\n\n", "\n\n")
            if system_prompt is not None:
                while "\n\n\n" in system_prompt:
                    system_prompt = system_prompt.replace("\n\n\n", "\n\n")
        system_prompt = LLM_SETTINGS.default_system_prompt if system_prompt is None else system_prompt
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
        ]
        messages.extend(former_messages[-1 * LLM_SETTINGS.max_past_message_include :])
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            },
        )
        return messages

    def build_messages_and_create_chat_completion(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        former_messages: list | None = None,
        chat_cache_prefix: str = "",
        *,
        shrink_multiple_break: bool = False,
        **kwargs: Any,
    ) -> str:
        if former_messages is None:
            former_messages = []
        messages = self.build_messages(
            user_prompt,
            system_prompt,
            former_messages,
            shrink_multiple_break=shrink_multiple_break,
        )
        return self._try_create_chat_completion_or_embedding(
            messages=messages,
            chat_completion=True,
            chat_cache_prefix=chat_cache_prefix,
            **kwargs,
        )

    def create_embedding(self, input_content: str | list[str], **kwargs: Any) -> list[Any] | Any:
        input_content_list = [input_content] if isinstance(input_content, str) else input_content
        resp = self._try_create_chat_completion_or_embedding(
            input_content_list=input_content_list,
            embedding=True,
            **kwargs,
        )
        if isinstance(input_content, str):
            return resp[0]
        return resp

    def _create_chat_completion_auto_continue(self, messages: list, **kwargs: dict) -> str:
        """
        Call the chat completion function and automatically continue the conversation if the finish_reason is length.
        TODO: This function only continues once, maybe need to continue more than once in the future.
        """
        # A truncated JSON document must be regenerated as a whole. Never append
        # a fresh JSON object to a partial one or continue an empty answer.
        request_kwargs = dict(kwargs)
        budget = request_kwargs.get("max_tokens") or LLM_SETTINGS.chat_max_tokens
        for attempt in range(2):
            response, finish_reason = self._create_chat_completion_inner_function(
                messages=messages, **request_kwargs
            )
            if finish_reason == "length":
                if attempt == 0:
                    request_kwargs["max_tokens"] = min(budget * 2, 32768)
                    request_kwargs["seed"] = random.randint(0, 2**31 - 1)
                    logger.warning("Model output truncated; regenerating with a larger token budget")
                    continue
                raise RuntimeError("Model output still truncated after increasing token budget")
            if not response or not response.strip():
                raise ValueError("Model returned empty content; check reasoning budget and endpoint")
            return response
        raise RuntimeError("No complete model response")

    def _try_create_chat_completion_or_embedding(
        self,
        max_retry: int = 10,
        *,
        chat_completion: bool = False,
        embedding: bool = False,
        **kwargs: Any,
    ) -> Any:
        assert not (chat_completion and embedding), "chat_completion and embedding cannot be True at the same time"
        max_retry = LLM_SETTINGS.max_retry if LLM_SETTINGS.max_retry is not None else max_retry
        last_error: Exception | None = None
        for i in range(max_retry):
            try:
                # import pdb; pdb.set_trace()
                if embedding:
                    return self._create_embedding_inner_function(**kwargs)
                if chat_completion:
                    return self._create_chat_completion_auto_continue(**kwargs)
            except openai.BadRequestError as e:  # noqa: PERF203
                last_error = e
                logger.warning(e)
                logger.warning(f"Retrying {i+1}th time...")
                if "'messages' must contain the word 'json' in some form" in e.message:
                    kwargs["add_json_in_prompt"] = True
                elif embedding and "maximum context length" in e.message:
                    kwargs["input_content_list"] = [
                        content[: len(content) // 2] for content in kwargs.get("input_content_list", [])
                    ]
                # Wait before retry to avoid rate limit
                if i < max_retry - 1:
                    time.sleep(self.retry_wait_seconds)
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning(e)
                logger.warning(f"Retrying {i+1}th time...")
                if i < max_retry - 1:
                    time.sleep(self.retry_wait_seconds)
        detail = (
            f" Last error: {type(last_error).__name__}: {last_error}"
            if last_error is not None
            else ""
        )
        error_message = f"Failed to create chat completion after {max_retry} retries.{detail}"
        raise RuntimeError(error_message)

    def _create_embedding_inner_function(
        self, input_content_list: list[str], **kwargs: Any
    ) -> list[Any]:  # noqa: ARG002
        if not self.embedding_model or not self.embedding_api_key or self.embedding_client is None:
            # When no embedding service is explicitly configured, use a
            # deterministic local representation.  Chat-only gateways such as
            # Agent Gateway must not receive unsupported /embeddings requests.
            from sklearn.feature_extraction.text import HashingVectorizer

            vectorizer = HashingVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                n_features=2048,
                alternate_sign=False,
                norm="l2",
            )
            return vectorizer.transform(input_content_list).toarray().tolist()
        content_to_embedding_dict = {}
        filtered_input_content_list = []
        if self.use_embedding_cache:
            for content in input_content_list:
                cache_result = self.cache.embedding_get(content)
                if cache_result is not None:
                    content_to_embedding_dict[content] = cache_result
                else:
                    filtered_input_content_list.append(content)
        else:
            filtered_input_content_list = input_content_list

        if len(filtered_input_content_list) > 0:
            # Adjust batch size by model (DashScope text-embedding-v4 is slower)
            batch_size = LLM_SETTINGS.embedding_max_str_num
            if self.embedding_model and ("qwen" in self.embedding_model.lower() or "text-embedding-v4" in self.embedding_model.lower()):
                # DashScope embedding: use smaller batch to avoid overload
                batch_size = min(batch_size, 3)
                # DashScope embedding: smaller batch (silent)
            
            batch_wait_seconds = LLM_SETTINGS.embedding_batch_wait_seconds
            batches = [
                filtered_input_content_list[i : i + batch_size]
                for i in range(0, len(filtered_input_content_list), batch_size)
            ]
            
            for batch_idx, sliced_filtered_input_content_list in enumerate(batches):
                if self.use_azure:
                    response = self.embedding_client.embeddings.create(
                        model=self.embedding_model,
                        input=sliced_filtered_input_content_list,
                    )
                else:
                    response = self.embedding_client.embeddings.create(
                        model=self.embedding_model,
                        input=sliced_filtered_input_content_list,
                    )
                for index, data in enumerate(response.data):
                    content_to_embedding_dict[sliced_filtered_input_content_list[index]] = data.embedding

                if self.dump_embedding_cache:
                    self.cache.embedding_set(content_to_embedding_dict)
                
                # Wait between batches to avoid API overload
                if batch_idx < len(batches) - 1 and batch_wait_seconds > 0:
                    time.sleep(batch_wait_seconds)
        return [content_to_embedding_dict[content] for content in input_content_list]

    def _build_log_messages(self, messages: list[dict], max_prompt_length: int = 100) -> str:
        """Build log string from messages (content truncated to max_prompt_length)."""
        log_messages = ""
        for m in messages:
            role = m['role']
            content = m['content']
            if len(content) > max_prompt_length:
                display_content = content[:max_prompt_length] + f"... [{len(content)} chars]"
            else:
                display_content = content
            
            log_messages += (
                f"\n{LogColors.MAGENTA}{LogColors.BOLD}Role:{LogColors.END}"
                f"{LogColors.CYAN}{role}{LogColors.END}\n"
                f"{LogColors.MAGENTA}{LogColors.BOLD}Content:{LogColors.END} "
                f"{LogColors.CYAN}{display_content}{LogColors.END}\n"
            )
        return log_messages

    @staticmethod
    def _resolve_codex_cli_command() -> str:
        configured = LLM_SETTINGS.codex_cli_command.strip()
        candidates = [configured] if configured else ["codex.exe", "codex"]
        for candidate in candidates:
            candidate_path = Path(candidate).expanduser()
            if candidate_path.is_file():
                return str(candidate_path)
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        # systemd/user services in WSL often do not inherit the Windows PATH
        # entries that an interactive WSL shell receives. Codex Desktop keeps
        # its versioned CLI beneath LocalAppData, so discover the newest local
        # installation directly when PATH lookup is unavailable.
        if not configured and Path("/mnt/c/Users").is_dir():
            discovered = list(
                Path("/mnt/c/Users").glob(
                    "*/AppData/Local/OpenAI/Codex/bin/*/codex.exe"
                )
            )
            discovered.sort(
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if discovered:
                return str(discovered[0])

        requested = configured or "codex/codex.exe"
        raise RuntimeError(
            f"Codex CLI executable not found ({requested}). Install/open Codex on Windows "
            "and ensure its bin directory is visible in WSL PATH."
        )

    @staticmethod
    def _resolve_claude_cli_command() -> str:
        configured = LLM_SETTINGS.claude_cli_command.strip()
        candidates = [configured] if configured else ["claude", "claude.exe"]
        for candidate in candidates:
            candidate_path = Path(candidate).expanduser()
            if candidate_path.is_file():
                return str(candidate_path)
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        if not configured and Path("/mnt/c/Users").is_dir():
            discovered = list(Path("/mnt/c/Users").glob("*/AppData/Roaming/npm/claude"))
            discovered += list(Path("/mnt/c/Users").glob("*/AppData/Roaming/npm/claude.cmd"))
            discovered.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            if discovered:
                return str(discovered[0])

        requested = configured or "claude"
        raise RuntimeError(
            f"Claude CLI executable not found ({requested}). Install Claude Code and sign in locally first."
        )

    def _create_claude_cli_completion(self, messages: list[dict], *, json_mode: bool) -> str:
        """Run one stateless, tool-free Claude CLI turn and return its result."""
        system_prompt = (
            "Answer the supplied conversation as a general language model. "
            "Return only the requested answer. Do not inspect files, run tools, or discuss this wrapper."
        )
        prompt_parts = ["Follow the conversation messages below and return only the assistant response."]
        if json_mode:
            prompt_parts.append("Return one valid JSON object only, with no Markdown code fence or surrounding prose.")
        prompt_parts.append("\nConversation:")
        for message in messages:
            role = str(message.get("role", "user")).upper()
            content = message.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            prompt_parts.append(f"\n<{role}>\n{content}\n</{role}>")
        prompt_parts.append("\n<ASSISTANT>\n")
        prompt = "\n".join(prompt_parts)

        command = [
            self._resolve_claude_cli_command(),
            "--print",
            "--safe-mode",
            "--system-prompt", system_prompt,
            "--output-format", "json",
            "--permission-mode", "dontAsk",
            "--tools", "",
            "--no-session-persistence",
        ]
        if LLM_SETTINGS.claude_cli_model.strip():
            command.extend(["--model", LLM_SETTINGS.claude_cli_model.strip()])

        run_kwargs: dict[str, Any] = {
            "input": prompt.encode("utf-8"),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": LLM_SETTINGS.claude_cli_timeout_seconds,
            "check": False,
        }
        if LLM_SETTINGS.claude_cli_workdir.strip():
            run_kwargs["cwd"] = LLM_SETTINGS.claude_cli_workdir.strip()

        cli_env = os.environ.copy()
        cli_env.pop("ANTHROPIC_API_KEY", None)
        cli_env.pop("ANTHROPIC_BASE_URL", None)
        run_kwargs["env"] = cli_env

        try:
            completed = subprocess.run(command, **run_kwargs)  # noqa: S603
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Claude CLI timed out after {LLM_SETTINGS.claude_cli_timeout_seconds} seconds."
            ) from exc

        stdout = completed.stdout.decode("utf-8", errors="replace").strip()
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        try:
            payload = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Claude CLI returned invalid JSON: {stdout[-2000:]}") from exc

        result = payload.get("result")
        if completed.returncode != 0 or payload.get("is_error") or not isinstance(result, str) or not result.strip():
            details = stderr or payload.get("result") or stdout
            raise RuntimeError(
                f"Claude CLI failed with exit code {completed.returncode}: {str(details)[-2000:]}"
            )
        if json_mode:
            result = json.dumps(robust_json_parse(result), ensure_ascii=False)
        return result

    def _create_codex_cli_completion(self, messages: list[dict], *, json_mode: bool) -> str:
        """Run one stateless Codex CLI turn and return its final assistant message."""
        prompt_parts = [
            "Act only as the language-model backend for QuantaAlpha.",
            "Do not inspect or modify files, do not run commands, and do not explain this wrapper.",
            "Follow the conversation messages below and return only the assistant response.",
        ]
        if json_mode:
            prompt_parts.append("Return one valid JSON object only, with no Markdown code fence or surrounding prose.")
        prompt_parts.append("\nConversation:")
        for message in messages:
            role = str(message.get("role", "user")).upper()
            content = message.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            prompt_parts.append(f"\n<{role}>\n{content}\n</{role}>")
        prompt_parts.append("\n<ASSISTANT>\n")
        prompt = "\n".join(prompt_parts)

        command = [
            self._resolve_codex_cli_command(),
            "--ask-for-approval",
            "never",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--json",
        ]
        if LLM_SETTINGS.codex_cli_model.strip():
            command.extend(["--model", LLM_SETTINGS.codex_cli_model.strip()])
        command.append("-")

        run_kwargs: dict[str, Any] = {
            "input": prompt.encode("utf-8"),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": LLM_SETTINGS.codex_cli_timeout_seconds,
            "check": False,
        }
        if LLM_SETTINGS.codex_cli_workdir.strip():
            run_kwargs["cwd"] = LLM_SETTINGS.codex_cli_workdir.strip()

        # Do not let QuantaAlpha's API credentials override the existing local
        # Codex/ChatGPT login inherited by codex.exe.
        cli_env = os.environ.copy()
        cli_env.pop("OPENAI_API_KEY", None)
        cli_env.pop("OPENAI_BASE_URL", None)
        run_kwargs["env"] = cli_env

        try:
            completed = subprocess.run(command, **run_kwargs)  # noqa: S603
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Codex CLI timed out after {LLM_SETTINGS.codex_cli_timeout_seconds} seconds."
            ) from exc

        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        assistant_messages: list[str] = []
        reported_errors: list[str] = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item") or {}
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    assistant_messages.append(text)
            if event.get("type") in {"error", "turn.failed"}:
                reported_errors.append(json.dumps(event, ensure_ascii=False))

        if completed.returncode != 0 or not assistant_messages:
            details = "\n".join(reported_errors) or stderr.strip() or stdout.strip()
            raise RuntimeError(
                f"Codex CLI failed with exit code {completed.returncode}: {details[-2000:]}"
            )
        return assistant_messages[-1]

    def _create_chat_completion_inner_function(  # noqa: C901, PLR0912, PLR0915
        self,
        messages: list[dict],
        reasoning_flag = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        chat_cache_prefix: str = "",
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        *,
        json_mode: bool = False,
        add_json_in_prompt: bool = False,
        seed: Optional[int] = None,
    ) -> str:
        """
        seed : Optional[int]
            When retrying with cache enabled, it will keep returning the same results.
            To make retries useful, we need to enable a seed.
            This seed is different from `self.chat_seed` for GPT. It is for the local cache mechanism enabled by QuantaAlpha locally.
        """
        if seed is None and LLM_SETTINGS.use_auto_chat_cache_seed_gen:
            seed = LLM_CACHE_SEED_GEN.get_next_seed()

        # TODO: we can add this function back to avoid so much `self.cfg.log_llm_chat_content`
        if LLM_SETTINGS.log_llm_chat_content:
            logger.info(self._build_log_messages(messages), tag="llm_messages")
        # TODO: fail to use loguru adaptor due to stream response
        input_content_json = json.dumps(messages)
        input_content_json = (
            chat_cache_prefix + input_content_json + f"<seed={seed}/>"
        )  # FIXME this is a hack to make sure the cache represents the round index
        if self.use_chat_cache:
            cache_result = self.cache.chat_get(input_content_json)
            if isinstance(cache_result, str) and cache_result.strip():
                if LLM_SETTINGS.log_llm_chat_content:
                    display_cr = cache_result[:200] + f"... [{len(cache_result)} chars]" if len(cache_result) > 200 else cache_result
                    logger.info(f"{LogColors.CYAN}Response(cached):{display_cr}{LogColors.END}", tag="llm_messages")
                return cache_result, None

        if temperature is None:
            temperature = LLM_SETTINGS.chat_temperature
        if max_tokens is None:
            max_tokens = LLM_SETTINGS.chat_max_tokens
        if frequency_penalty is None:
            frequency_penalty = LLM_SETTINGS.chat_frequency_penalty
        if presence_penalty is None:
            presence_penalty = LLM_SETTINGS.chat_presence_penalty

        # Use index 4 to skip the current function and intermediate calls,
        # and get the locals of the caller's frame.
        caller_locals = inspect.stack()[4].frame.f_locals
        if "self" in caller_locals:
            tag = caller_locals["self"].__class__.__name__
        else:
            tag = inspect.stack()[4].function
            
        if reasoning_flag:
            model = self.reasoning_model
            json_mode = None
        else:
            model = self.chat_model_map.get(tag, self.chat_model)

        finish_reason = None
        expects_json = bool(json_mode or reasoning_flag)
        if self.use_llama2:
            response = self.generator.chat_completion(
                messages,  # type: ignore
                max_gen_len=max_tokens,
                temperature=temperature,
            )
            resp = response[0]["generation"]["content"]
            if LLM_SETTINGS.log_llm_chat_content:
                logger.info(f"{LogColors.CYAN}Response:{resp}{LogColors.END}", tag="llm_messages")
        elif self.use_gcr_endpoint:
            body = str.encode(
                json.dumps(
                    {
                        "input_data": {
                            "input_string": messages,
                            "parameters": {
                                "temperature": self.gcr_endpoint_temperature,
                                "top_p": self.gcr_endpoint_top_p,
                                "max_new_tokens": self.gcr_endpoint_max_token,
                            },
                        },
                    },
                ),
            )

            req = urllib.request.Request(self.gcr_endpoint, body, self.headers)  # noqa: S310
            response = urllib.request.urlopen(req)  # noqa: S310
            resp = json.loads(response.read().decode())["output"]
            if LLM_SETTINGS.log_llm_chat_content:
                logger.info(f"{LogColors.CYAN}Response:{resp}{LogColors.END}", tag="llm_messages")
        elif self.use_codex_cli:
            resp = self._create_codex_cli_completion(messages, json_mode=expects_json)
            finish_reason = "stop"
            if LLM_SETTINGS.log_llm_chat_content:
                display_resp = resp[:200] + f"... [{len(resp)} chars]" if len(resp) > 200 else resp
                logger.info(f"{LogColors.CYAN}Response(Codex CLI):{display_resp}{LogColors.END}", tag="llm_messages")
        elif self.use_claude_cli:
            resp = self._create_claude_cli_completion(messages, json_mode=expects_json)
            finish_reason = "stop"
            if LLM_SETTINGS.log_llm_chat_content:
                display_resp = resp[:200] + f"... [{len(resp)} chars]" if len(resp) > 200 else resp
                logger.info(f"{LogColors.CYAN}Response(Claude CLI):{display_resp}{LogColors.END}", tag="llm_messages")
        else:
            kwargs = dict(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=self.chat_stream,
                seed=self.chat_seed,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            
            if json_mode:
                if add_json_in_prompt:
                    for message in messages[::-1]:
                        message["content"] = message["content"] + "\nPlease respond in json format."
                        if message["role"] == "system":
                            break
                kwargs["response_format"] = {"type": "json_object"}
            extra_body = os.environ.get("QUANTAALPHA_CHAT_EXTRA_BODY")
            if extra_body:
                kwargs["extra_body"] = json.loads(extra_body)
            response = self.chat_client.chat.completions.create(**kwargs)

            
            if self.chat_stream:
                resp = ""
                for chunk in response:
                    content = (
                        chunk.choices[0].delta.content
                        if len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None
                        else ""
                    )
                    resp += content
                    if len(chunk.choices) > 0 and chunk.choices[0].finish_reason is not None:
                        finish_reason = chunk.choices[0].finish_reason

                if LLM_SETTINGS.log_llm_chat_content:
                    display_resp = resp[:200] + f"... [{len(resp)} chars]" if len(resp) > 200 else resp
                    logger.info(f"{LogColors.CYAN}Response:{display_resp}{LogColors.END}", tag="llm_messages")

            else:
                resp = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                if LLM_SETTINGS.log_llm_chat_content:
                    display_resp = resp[:200] + f"... [{len(resp)} chars]" if len(resp) > 200 else resp
                    logger.info(f"{LogColors.CYAN}Response:{display_resp}{LogColors.END}", tag="llm_messages")
                    logger.info(
                        json.dumps(
                            {
                                "tag": tag,
                                "total_tokens": response.usage.total_tokens,
                                "prompt_tokens": response.usage.prompt_tokens,
                                "completion_tokens": response.usage.completion_tokens,
                                "model": model,
                            }
                        ),
                        tag="llm_messages",
                    )
            logger.info(f"Model response: finish_reason={finish_reason}, content_chars={len(resp or '')}")
            if finish_reason != "length":
                if not resp or not resp.strip():
                    raise ValueError("Model returned empty content; check reasoning budget and endpoint")
                if json_mode or reasoning_flag:
                    resp = json.dumps(robust_json_parse(resp), ensure_ascii=False)
        if self.dump_chat_cache and finish_reason != "length" and resp and resp.strip():
            self.cache.chat_set(input_content_json, resp)
        return resp, finish_reason

    def calculate_token_from_messages(self, messages: list[dict]) -> int:
        return 0
        if self.use_llama2 or self.use_gcr_endpoint:
            logger.warning("num_tokens_from_messages() is not implemented for model llama2.")
            return 0  # TODO implement this function for llama2

        if "gpt4" in self.chat_model or "gpt-4" in self.chat_model:
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            tokens_per_message = 4  # every message follows <start>{role/name}\n{content}<end>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(self.encoder.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <start>assistant<message>
        return num_tokens

    def build_messages_and_calculate_token(
        self,
        user_prompt: str,
        system_prompt: str | None,
        former_messages: list[dict] | None = None,
        *,
        shrink_multiple_break: bool = False,
    ) -> int:
        if former_messages is None:
            former_messages = []
        messages = self.build_messages(
            user_prompt, system_prompt, former_messages, shrink_multiple_break=shrink_multiple_break
        )
        return self.calculate_token_from_messages(messages)


def calculate_embedding_distance_between_str_list(
    source_str_list: list[str],
    target_str_list: list[str],
) -> list[list[float]]:
    if not source_str_list or not target_str_list:
        return [[]]

    embeddings = APIBackend().create_embedding(source_str_list + target_str_list)

    source_embeddings = embeddings[: len(source_str_list)]
    target_embeddings = embeddings[len(source_str_list) :]

    source_embeddings_np = np.array(source_embeddings)
    target_embeddings_np = np.array(target_embeddings)

    source_embeddings_np = source_embeddings_np / np.linalg.norm(source_embeddings_np, axis=1, keepdims=True)
    target_embeddings_np = target_embeddings_np / np.linalg.norm(target_embeddings_np, axis=1, keepdims=True)
    similarity_matrix = np.dot(source_embeddings_np, target_embeddings_np.T)

    return similarity_matrix.tolist()

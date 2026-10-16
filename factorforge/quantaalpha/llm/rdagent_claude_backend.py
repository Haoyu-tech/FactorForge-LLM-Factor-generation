"""RDAgent-compatible backend that routes chat completions through Claude CLI."""

from __future__ import annotations

import json
from typing import Any, Optional, Type, Union

from pydantic import BaseModel
from rdagent.oai.backend.base import APIBackend as RDAgentAPIBackend

from quantaalpha.llm.client import APIBackend as QuantaAlphaAPIBackend


class ClaudeCLIAPIBackend(RDAgentAPIBackend):
    """Make RDAgent's APIBackend interface use the local Claude CLI bridge."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._delegate = QuantaAlphaAPIBackend(
            use_chat_cache=False,
            dump_chat_cache=False,
            use_embedding_cache=False,
            dump_embedding_cache=False,
        )

    def supports_response_schema(self) -> bool:
        return True

    def _calculate_token_from_messages(self, messages: list[dict[str, Any]]) -> int:
        content = json.dumps(messages, ensure_ascii=False)
        return max(1, len(content.encode("utf-8")) // 3)

    def _create_embedding_inner_function(self, input_content_list: list[str]) -> list[list[float]]:
        return self._delegate.create_embedding(input_content_list)

    def _create_chat_completion_inner_function(
        self,
        messages: list[dict[str, Any]],
        response_format: Optional[Union[dict, Type[BaseModel]]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[str, str | None]:
        del args, kwargs
        cli_messages = [dict(message) for message in messages]
        if response_format is not None and response_format != {"type": "json_object"}:
            if isinstance(response_format, dict):
                schema = response_format
            elif issubclass(response_format, BaseModel):
                schema = response_format.model_json_schema()
            else:
                schema = None
            if schema:
                cli_messages.append({
                    "role": "user",
                    "content": "Return JSON conforming exactly to this JSON Schema:\n" + json.dumps(schema, ensure_ascii=False),
                })
        response = self._delegate._create_claude_cli_completion(
            cli_messages,
            json_mode=response_format is not None,
        )
        return response, "stop"

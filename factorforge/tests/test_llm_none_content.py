"""Regression tests for reasoning models that return ``content=None``.

Qwen3-style thinking models can spend their whole ``max_tokens`` budget on
reasoning tokens and return ``choices[0].message.content is None`` together
with ``finish_reason="length"``.  The client must survive that response,
escalate the token budget, and surface a readable error when it cannot.
"""

from types import SimpleNamespace

import pytest

from quantaalpha.llm.client import APIBackend


def _response(content, finish_reason, *, completion_tokens=12000):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, reasoning_content=None),
                finish_reason=finish_reason,
                delta=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(
            total_tokens=completion_tokens + 100,
            prompt_tokens=100,
            completion_tokens=completion_tokens,
        ),
    )


def _backend(responses):
    """An APIBackend wired to a scripted sequence of gateway responses."""
    backend = object.__new__(APIBackend)
    backend.use_chat_cache = False
    backend.dump_chat_cache = False
    backend.use_llama2 = False
    backend.use_gcr_endpoint = False
    backend.use_codex_cli = False
    backend.use_claude_cli = False
    backend.chat_stream = False
    backend.chat_seed = None
    backend.chat_model = "qwen38-27b"
    backend.reasoning_model = "openai/qwen38-27b"
    backend.chat_model_map = {}
    backend.retry_wait_seconds = 0
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    backend.chat_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    backend.calls = calls
    return backend


def test_none_content_with_length_escalates_budget_instead_of_type_error():
    """content=None + finish_reason=length must trigger the retry-with-more-tokens path."""
    backend = _backend(
        [
            _response(None, "length"),
            _response('{"name": "momentum"}', "stop", completion_tokens=500),
        ]
    )

    result = backend.build_messages_and_create_chat_completion(
        user_prompt="design a factor",
        system_prompt="you are a quant",
        max_tokens=12000,
    )

    assert "momentum" in result
    assert len(backend.calls) == 2, "expected one escalated retry"
    assert backend.calls[1]["max_tokens"] > backend.calls[0]["max_tokens"], (
        "token budget must grow after a truncated reasoning response"
    )


def test_none_content_without_length_raises_readable_error():
    """content=None + finish_reason=stop must give an actionable message, not len(None)."""
    backend = _backend([_response(None, "stop")])

    with pytest.raises(RuntimeError) as excinfo:
        backend.build_messages_and_create_chat_completion(
            user_prompt="design a factor",
            system_prompt="you are a quant",
            max_tokens=12000,
        )

    message = str(excinfo.value)
    assert "has no len()" not in message, "cryptic TypeError leaked to the caller"
    assert "empty content" in message

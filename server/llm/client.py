from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

import anthropic
import httpx
from openai import OpenAI

from config import get_settings

_openai_lock = threading.Lock()
_anthropic_lock = threading.Lock()
_openai_client: OpenAI | None = None
_anthropic_client: anthropic.Anthropic | None = None


def _get_openai() -> OpenAI | None:
    """Reuse one OpenAI client (connection pooling, fewer TLS handshakes)."""
    global _openai_client
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        return None
    with _openai_lock:
        if _openai_client is None:
            _openai_client = OpenAI(
                api_key=key,
                timeout=httpx.Timeout(settings.llm_timeout_seconds),
            )
        return _openai_client


def _get_anthropic() -> anthropic.Anthropic | None:
    global _anthropic_client
    settings = get_settings()
    key = (settings.anthropic_api_key or "").strip()
    if not key:
        return None
    with _anthropic_lock:
        if _anthropic_client is None:
            _anthropic_client = anthropic.Anthropic(
                api_key=key,
                timeout=settings.llm_timeout_seconds,
            )
        return _anthropic_client


def complete_json_chat(system: str, user: str) -> tuple[dict[str, Any], str]:
    """Run a non-streaming JSON completion with retries and provider fallback."""
    from guardrails.llm_wrapper import safe_json_completion

    settings = get_settings()
    if not (settings.openai_api_key or "").strip() and not (
        settings.anthropic_api_key or ""
    ).strip():
        raise RuntimeError("No LLM API keys configured for JSON completion")
    return safe_json_completion(system, user)


class LLMClient:
    """Streams assistant text with OpenAI primary and Anthropic fallback."""

    def __init__(self) -> None:
        self.last_provider: str = "unknown"

    def stream_assistant(
        self,
        system: str,
        user_messages: list[dict[str, str]],
    ) -> Iterator[str]:
        from guardrails.llm_wrapper import safe_stream_assistant

        for prov, chunk in safe_stream_assistant(system, user_messages):
            self.last_provider = prov
            yield chunk

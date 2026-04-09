from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

from openai import APIError, APITimeoutError, RateLimitError

from config import get_settings
from llm.json_utils import parse_json_object

logger = logging.getLogger(__name__)

LLM_FALLBACK_USER_MESSAGE = (
    "Sorry, I'm having trouble responding right now. Please try again."
)


def safe_llm_call(prompt: str) -> str:
    """
    Spec-shaped helper: treat `prompt` as user text with a fixed safe system preamble.
    Prefer `safe_json_completion(system, user)` for structured agents.
    """
    system = (
        "You are a health-coach assistant. Reply with one short supportive sentence. "
        "Do not diagnose or prescribe."
    )
    data, _prov = safe_json_completion(system, prompt[:8000])
    text = data.get("reply") or data.get("message") or data.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return LLM_FALLBACK_USER_MESSAGE


def safe_json_completion(system: str, user: str) -> tuple[dict[str, Any], str]:
    """
    JSON chat completion with per-provider retries, then cross-provider fallback.
    Max attempts per provider = guardrail_json_retries (default 2).
    """
    from llm.client import _get_anthropic, _get_openai

    settings = get_settings()
    attempts = max(1, settings.guardrail_json_retries)
    last_err: Exception | None = None

    client = _get_openai()
    if client:
        for attempt in range(attempts):
            try:
                resp = client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content or "{}"
                data = parse_json_object(raw)
                return data, "openai"
            except json.JSONDecodeError as e:
                last_err = e
                logger.warning(
                    "guardrails: OpenAI JSON parse failed attempt=%s err=%s",
                    attempt + 1,
                    e,
                )
            except (APITimeoutError, APIError, RateLimitError) as e:
                last_err = e
                logger.warning(
                    "guardrails: OpenAI JSON completion failed attempt=%s err=%s",
                    attempt + 1,
                    e,
                )
            except Exception as e:
                last_err = e
                logger.warning(
                    "guardrails: OpenAI JSON unexpected error attempt=%s err=%s",
                    attempt + 1,
                    e,
                )
            if attempt < attempts - 1:
                time.sleep(0.35 * (attempt + 1))

    aclient = _get_anthropic()
    if not aclient:
        logger.error("guardrails: no LLM provider available: %s", last_err)
        return {}, "none"

    for attempt in range(attempts):
        try:
            msg = aclient.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                temperature=0.2,
                system=system
                + "\nRespond with a single valid JSON object only, no markdown.",
                messages=[{"role": "user", "content": user}],
            )
            raw = ""
            for block in msg.content:
                if block.type == "text":
                    raw += block.text
            data = parse_json_object(raw)
            return data, "anthropic"
        except json.JSONDecodeError as e:
            last_err = e
            logger.warning(
                "guardrails: Anthropic JSON parse failed attempt=%s err=%s",
                attempt + 1,
                e,
            )
        except Exception as e:
            last_err = e
            logger.warning(
                "guardrails: Anthropic JSON completion failed attempt=%s err=%s",
                attempt + 1,
                e,
            )
        if attempt < attempts - 1:
            time.sleep(0.35 * (attempt + 1))

    logger.error("guardrails: all JSON completion attempts failed: %s", last_err)
    return {}, "none"


def safe_stream_assistant(
    system: str,
    user_messages: list[dict[str, str]],
) -> Iterator[tuple[str, str]]:
    """
    Yields (provider_name, token_chunk). Falls back OpenAI → Anthropic → static text.
    Each provider gets up to guardrail_json_retries streaming attempts.
    """
    from llm.client import _get_anthropic, _get_openai

    settings = get_settings()
    attempts = max(1, settings.guardrail_json_retries)

    client = _get_openai()
    if client:
        for attempt in range(attempts):
            try:
                stream = client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "system", "content": system}, *user_messages],
                    stream=True,
                    temperature=0.7,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield "openai", delta.content
                return
            except (APITimeoutError, APIError, RateLimitError) as e:
                logger.warning(
                    "guardrails: OpenAI stream failed attempt=%s err=%s",
                    attempt + 1,
                    e,
                )
            except Exception as e:
                logger.warning(
                    "guardrails: OpenAI stream unexpected attempt=%s err=%s",
                    attempt + 1,
                    e,
                )
            if attempt < attempts - 1:
                time.sleep(0.35 * (attempt + 1))

    aclient = _get_anthropic()
    if aclient:
        anth_msgs = [{"role": m["role"], "content": m["content"]} for m in user_messages]
        for attempt in range(attempts):
            try:
                with aclient.messages.stream(
                    model=settings.anthropic_model,
                    max_tokens=2048,
                    temperature=0.7,
                    system=system,
                    messages=anth_msgs,
                ) as stream:
                    for text in stream.text_stream:
                        yield "anthropic", text
                return
            except Exception as e:
                logger.warning(
                    "guardrails: Anthropic stream failed attempt=%s err=%s",
                    attempt + 1,
                    e,
                )
                if attempt < attempts - 1:
                    time.sleep(0.35 * (attempt + 1))

    logger.error("guardrails: streaming exhausted all providers")
    yield "none", LLM_FALLBACK_USER_MESSAGE

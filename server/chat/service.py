from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from agents.intent import run_intent_agent
from agents.question_agent import run_question_agent
from agents.schemas import IntentOutput, QuestionAgentOutput
from chat.prompts import build_system_prompt
from config import get_settings
from db.models import Message
from guardrails.input_validation import PreparedUserMessage
from guardrails.output_filter import filter_output
from guardrails.safety_rules import check_safety
from llm.client import LLMClient
from memory.retrieval import build_memory_context
from onboarding.service import (
    GOAL_CHOICES,
    STATUS_COMPLETED,
    apply_onboarding_turn,
    ensure_coach_user,
    get_onboarding_meta,
    get_onboarding_status,
)
from protocol.engine import ProtocolEngine, ProtocolOutput
from prompts.service import get_prompt_content
from redis_client import cache_messages_delete
from streaming.sse import format_sse

logger = logging.getLogger(__name__)

_COACH_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="coach")


def shutdown_coach_executor() -> None:
    """Best-effort cleanup on app shutdown (Python 3.9+ cancel_futures)."""
    try:
        _COACH_POOL.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        _COACH_POOL.shutdown(wait=False)


def _build_llm_messages(short_term: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in short_term:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        out.append({"role": role, "content": content})
    return out[-30:]


def _finalize_short_circuit_reply(
    *,
    session: Session,
    user_id: str,
    user_msg: Message,
    reply: str,
    capture: dict[str, str] | None,
    llm: LLMClient,
) -> Iterator[str]:
    """Persist filtered assistant message and emit SSE tail (after meta + ui)."""
    filtered = filter_output(reply)
    if filtered != reply:
        logger.warning("guardrails: assistant reply modified by output_filter")

    if capture is not None:
        capture["assistant_text"] = filtered
        capture["skip_memory"] = "1"
        capture["user_message"] = user_msg.content

    asst = Message(user_id=user_id, role="assistant", content=filtered)
    session.add(asst)
    session.flush()

    yield format_sse({"type": "token", "text": filtered})

    yield format_sse(
        {
            "type": "done",
            "user_message_id": user_msg.id,
            "assistant_message_id": asst.id,
            "provider": llm.last_provider,
            "onboarding": get_onboarding_meta(session, user_id),
        }
    )


def run_chat_stream(
    session: Session,
    *,
    user_id: str,
    prepared: PreparedUserMessage,
    capture: dict[str, str] | None = None,
) -> Iterator[str]:
    settings = get_settings()
    llm = LLMClient()
    llm.last_provider = "guardrails"

    # --- Invalid / empty input (sanitization failed) ---
    if prepared.rejected:
        user_msg = Message(user_id=user_id, role="user", content=prepared.storage_text)
        session.add(user_msg)
        session.flush()
        assert prepared.immediate_assistant is not None
        yield format_sse(
            {
                "type": "meta",
                "user_message_id": user_msg.id,
                "user_content": prepared.storage_text,
            }
        )
        yield format_sse(
            {
                "type": "ui",
                "interactive": QuestionAgentOutput().model_dump(mode="json"),
            }
        )
        yield from _finalize_short_circuit_reply(
            session=session,
            user_id=user_id,
            user_msg=user_msg,
            reply=prepared.immediate_assistant,
            capture=capture,
            llm=llm,
        )
        return

    content = prepared.pipeline_text

    ensure_coach_user(session, user_id)

    user_msg = Message(user_id=user_id, role="user", content=prepared.storage_text)
    session.add(user_msg)
    session.flush()

    yield format_sse(
        {
            "type": "meta",
            "user_message_id": user_msg.id,
            "user_content": prepared.storage_text,
            "onboarding": get_onboarding_meta(session, user_id),
        }
    )

    safety = check_safety(content)
    if safety.get("override"):
        reply = str(safety.get("response") or "").strip() or filter_output("")
        yield format_sse(
            {
                "type": "ui",
                "interactive": QuestionAgentOutput().model_dump(mode="json"),
            }
        )
        yield from _finalize_short_circuit_reply(
            session=session,
            user_id=user_id,
            user_msg=user_msg,
            reply=reply,
            capture=capture,
            llm=llm,
        )
        return

    protocol_quick = ProtocolEngine().run(content, [])
    if (
        get_onboarding_status(session, user_id) != STATUS_COMPLETED
        and protocol_quick.protocol != "emergency"
    ):
        cache_messages_delete(user_id)
        try:
            reply_text, question_ui = apply_onboarding_turn(
                session, user_id, content, {}
            )
        except Exception:
            logger.exception("onboarding turn failed")
            reply_text = "Choose a focus below, or type your goal."
            question_ui = QuestionAgentOutput(
                interaction="choices",
                prompt="Pick one to continue.",
                choices=list(GOAL_CHOICES),
            )
        yield format_sse(
            {
                "type": "ui",
                "interactive": question_ui.model_dump(mode="json"),
            }
        )
        yield from _finalize_short_circuit_reply(
            session=session,
            user_id=user_id,
            user_msg=user_msg,
            reply=reply_text,
            capture=capture,
            llm=llm,
        )
        return

    cache_messages_delete(user_id)

    intent_future = _COACH_POOL.submit(run_intent_agent, content)
    try:
        mem_ctx, short_term_rows = build_memory_context(session, user_id, content)
        intent = intent_future.result(timeout=settings.llm_timeout_seconds + 45.0)
    except Exception:
        try:
            intent_future.result(timeout=settings.llm_timeout_seconds + 45.0)
        except Exception:
            pass
        logger.exception("memory or intent path failed")
        yield format_sse(
            {
                "type": "stream_error",
                "message": "Could not prepare a reply. Please try again.",
                "partial": False,
            }
        )
        yield format_sse(
            {
                "type": "ui",
                "interactive": QuestionAgentOutput().model_dump(mode="json"),
            }
        )
        yield from _finalize_short_circuit_reply(
            session=session,
            user_id=user_id,
            user_msg=user_msg,
            reply="Sorry, I couldn't process that. Please try again.",
            capture=capture,
            llm=llm,
        )
        return

    protocol_engine = ProtocolEngine()
    protocol = protocol_engine.run(content, intent.entities)
    intent = _maybe_boost_emergency_intent(intent, protocol)

    question_ui = run_question_agent(content, intent, protocol)
    yield format_sse(
        {
            "type": "ui",
            "interactive": question_ui.model_dump(mode="json"),
        }
    )

    preamble = get_prompt_content("coach_system_preamble")
    system = build_system_prompt(
        preamble,
        mem_ctx.profile,
        mem_ctx.summary,
        mem_ctx.episodic,
        intent,
        protocol,
    )
    user_messages = _build_llm_messages(short_term_rows)

    full_reply: list[str] = []

    try:
        for token in llm.stream_assistant(system, user_messages):
            full_reply.append(token)
            yield format_sse({"type": "token", "text": token})
    except Exception as e:
        logger.exception("stream failed")
        partial = "".join(full_reply)
        yield format_sse(
            {
                "type": "stream_error",
                "message": "Stream interrupted.",
                "partial": bool(partial.strip()),
            }
        )
        err = (
            "Sorry — something went wrong while replying. Please try again."
            if not partial.strip()
            else f"{partial}\n\n(Something went wrong — please try again.)"
        )
        full_reply.clear()
        full_reply.append(err)
        yield format_sse({"type": "token", "text": err})

    text = "".join(full_reply)
    filtered = filter_output(text)
    if filtered != text:
        logger.warning("guardrails: streamed reply post-filtered before persistence")

    if capture is not None:
        capture["assistant_text"] = filtered
        capture["user_message"] = prepared.storage_text

    asst = Message(user_id=user_id, role="assistant", content=filtered)
    session.add(asst)
    session.flush()

    yield format_sse(
        {
            "type": "done",
            "user_message_id": user_msg.id,
            "assistant_message_id": asst.id,
            "provider": llm.last_provider,
            "onboarding": get_onboarding_meta(session, user_id),
        }
    )


def _maybe_boost_emergency_intent(
    intent: IntentOutput, protocol: ProtocolOutput
) -> IntentOutput:
    if protocol.protocol == "emergency" or protocol.priority == "high":
        return IntentOutput(
            intent="emergency",
            entities=intent.entities,
            urgency="high",
        )
    return intent

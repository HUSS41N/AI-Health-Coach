from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from config import get_settings
from db.models import EpisodicMemory, Message
from memory.episodic import extract_tags
from memory.long_term import load_profile_db
from memory.schemas import MemoryContext
from memory.summary import load_summary_db
from redis_client import (
    cache_messages_delete,
    cache_messages_get,
    cache_messages_set,
    profile_cache_delete,
    profile_cache_get,
    profile_cache_set,
    summary_cache_delete,
    summary_cache_get,
    summary_cache_set,
)

logger = logging.getLogger(__name__)


def _fetch_recent_messages(session: Session, user_id: str, limit: int) -> list[Message]:
    stmt: Select[tuple[Message]] = (
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list(session.scalars(stmt).all())
    return list(reversed(rows))


def load_short_term_messages(session: Session, user_id: str, limit: int) -> list[dict[str, Any]]:
    cached = cache_messages_get(user_id)
    if cached is not None:
        return cached
    rows = _fetch_recent_messages(session, user_id, limit)
    payload = [{"role": r.role, "content": r.content, "id": r.id} for r in rows]
    cache_messages_set(user_id, payload)
    return payload


def get_profile_for_context(session: Session, user_id: str) -> dict[str, Any]:
    raw = profile_cache_get(user_id)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    profile = load_profile_db(session, user_id)
    profile_cache_set(user_id, json.dumps(profile))
    return profile


def get_summary_for_context(session: Session, user_id: str) -> str | None:
    raw = summary_cache_get(user_id)
    if raw is not None:
        return raw if raw.strip() else None
    text = load_summary_db(session, user_id)
    if text:
        summary_cache_set(user_id, text)
    return text


def retrieve_episodic(
    session: Session,
    user_id: str,
    message: str,
    *,
    match_limit: int = 5,
    fallback_limit: int = 3,
) -> list[str]:
    keywords = extract_tags(message)
    if keywords:
        try:
            stmt = (
                select(EpisodicMemory.content)
                .where(
                    EpisodicMemory.user_id == user_id,
                    EpisodicMemory.tags.overlap(keywords),
                )
                .order_by(EpisodicMemory.created_at.desc())
                .limit(match_limit)
            )
            rows = list(session.scalars(stmt).all())
            if rows:
                return list(rows)
        except Exception:
            logger.exception("episodic overlap query failed, using fallback")

    stmt_fb = (
        select(EpisodicMemory.content)
        .where(EpisodicMemory.user_id == user_id)
        .order_by(EpisodicMemory.created_at.desc())
        .limit(fallback_limit)
    )
    return list(session.scalars(stmt_fb).all())


def build_memory_context(
    session: Session,
    user_id: str,
    current_message: str,
) -> tuple[MemoryContext, list[dict[str, Any]]]:
    """Returns (context for prompts, full short-term rows for the main LLM).

    Single ``load_short_term_messages`` call — avoids duplicate Redis/DB work
    where ``short_term_message_limit`` equals the window used for context slicing.
    """
    settings = get_settings()
    st_lim = settings.short_term_message_limit
    ctx_lim = settings.memory_context_message_limit
    recent_full = load_short_term_messages(session, user_id, st_lim)
    recent_ctx = (
        recent_full[-ctx_lim:] if len(recent_full) > ctx_lim else list(recent_full)
    )
    summary = get_summary_for_context(session, user_id)
    profile = get_profile_for_context(session, user_id)
    episodic = retrieve_episodic(session, user_id, current_message)
    mem = MemoryContext(
        recent_messages=recent_ctx,
        summary=summary,
        profile=profile,
        episodic=episodic,
    )
    return mem, recent_full


def invalidate_user_memory_caches(user_id: str) -> None:
    cache_messages_delete(user_id)
    profile_cache_delete(user_id)
    summary_cache_delete(user_id)

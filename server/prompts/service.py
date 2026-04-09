from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import AgentPrompt
from db.session import get_session_factory
from prompts.defaults import PROMPT_DEFAULTS
from redis_client import prompt_cache_delete, prompt_cache_get, prompt_cache_set

logger = logging.getLogger(__name__)

_local_lock = threading.Lock()
_local_prompts: dict[str, str] = {}


def invalidate_local_prompt_cache(key: str | None = None) -> None:
    """Clear in-process prompt cache (call after admin PATCH)."""
    with _local_lock:
        if key is None:
            _local_prompts.clear()
        else:
            _local_prompts.pop(key, None)


def _default_for_key(key: str) -> str:
    pair = PROMPT_DEFAULTS.get(key)
    return pair[1] if pair else ""


def get_prompt_content(key: str) -> str:
    """Resolved prompt text: process cache → Redis → DB → built-in default."""
    with _local_lock:
        local_hit = _local_prompts.get(key)
    if local_hit is not None:
        return local_hit

    cached = prompt_cache_get(key)
    if cached is not None:
        with _local_lock:
            _local_prompts[key] = cached
        return cached

    factory = get_session_factory()
    session = factory()
    try:
        row = session.get(AgentPrompt, key)
        if row and row.content and row.content.strip():
            text = row.content
            prompt_cache_set(key, text)
            with _local_lock:
                _local_prompts[key] = text
            return text
    finally:
        session.close()

    text = _default_for_key(key)
    with _local_lock:
        _local_prompts[key] = text
    return text


def warm_agent_prompts() -> None:
    """Load all default keys once at startup (fewer Redis round-trips on first chat)."""
    for k in PROMPT_DEFAULTS:
        try:
            get_prompt_content(k)
        except Exception:
            logger.debug("warm prompt %s skipped", k, exc_info=True)


def seed_prompts_if_needed() -> None:
    """Insert missing `agent_prompts` rows with default content."""
    factory = get_session_factory()
    session = factory()
    try:
        for key, (title, content) in PROMPT_DEFAULTS.items():
            row = session.get(AgentPrompt, key)
            if row is None:
                now = datetime.now(timezone.utc)
                session.add(
                    AgentPrompt(
                        key=key,
                        title=title,
                        content=content,
                        updated_at=now,
                    ),
                )
        session.commit()
        logger.info("Agent prompts table seeded (missing keys only)")
    except Exception:
        session.rollback()
        logger.exception("seed_prompts_if_needed failed")
    finally:
        session.close()


def upsert_prompt(session: Session, key: str, content: str) -> AgentPrompt:
    """Create or update a prompt row (admin). Caller should commit."""
    text = content.strip()
    if not text:
        raise ValueError("content cannot be empty")
    now = datetime.now(timezone.utc)
    row = session.get(AgentPrompt, key)
    if row:
        row.content = text
        row.updated_at = now
    else:
        title, default_body = PROMPT_DEFAULTS.get(key, (key.replace("_", " ").title(), ""))
        row = AgentPrompt(key=key, title=title, content=text or default_body, updated_at=now)
        session.add(row)
    invalidate_local_prompt_cache(key)
    prompt_cache_delete(key)
    return row


def list_prompt_rows(session: Session) -> list[AgentPrompt]:
    return list(session.scalars(select(AgentPrompt).order_by(AgentPrompt.key)).all())

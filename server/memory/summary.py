from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import get_settings
from db.models import ConversationSummary, MemoryRow, Message
from llm.client import complete_json_chat
from prompts.service import get_prompt_content

logger = logging.getLogger(__name__)


def load_summary_db(session: Session, user_id: str) -> str | None:
    row = session.get(ConversationSummary, user_id)
    if row and row.summary and row.summary.strip():
        return row.summary.strip()
    legacy = session.scalars(
        select(MemoryRow)
        .where(MemoryRow.user_id == user_id, MemoryRow.type == "summary")
        .order_by(MemoryRow.id.desc())
        .limit(1)
    ).first()
    if legacy and isinstance(legacy.content, dict):
        t = legacy.content.get("text") or legacy.content.get("summary")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return None


def upsert_summary(session: Session, user_id: str, summary_text: str) -> None:
    text = summary_text.strip()
    if not text:
        return
    now = datetime.now(timezone.utc)
    row = session.get(ConversationSummary, user_id)
    if row:
        row.summary = text
        row.updated_at = now
    else:
        session.add(
            ConversationSummary(user_id=user_id, summary=text, updated_at=now),
        )


def update_summary_llm(
    old_summary: str | None,
    recent_messages: list[tuple[str, str]],
) -> str:
    """Compress prior summary + new lines into one concise summary."""
    lines = [f"{role}: {content}" for role, content in recent_messages]
    transcript = "\n".join(lines)[-10000:]
    prev = (old_summary or "").strip() or "(none yet)"
    system = get_prompt_content("conversation_summary")
    user = f"Previous summary:\n{prev}\n\nNew messages:\n{transcript}"
    try:
        data, _ = complete_json_chat(system, user)
        text = data.get("summary") or data.get("text")
        if not text:
            return prev if prev != "(none yet)" else ""
        return str(text).strip()
    except Exception as e:
        logger.warning("update_summary_llm failed: %s", e)
        return old_summary or ""


def maybe_refresh_summary_for_user(session: Session, user_id: str) -> None:
    settings = get_settings()
    n = session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.user_id == user_id, Message.role == "user")
    )
    n = int(n or 0)
    if n == 0:
        return
    k = settings.summary_every_n_user_messages
    if n % k != 0:
        return

    recent_rows = list(
        session.scalars(
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(40)
        ).all()
    )
    recent_rows.reverse()
    recent_pairs = [(m.role, m.content) for m in recent_rows]
    old = load_summary_db(session, user_id)
    new_text = update_summary_llm(old, recent_pairs)
    if new_text:
        upsert_summary(session, user_id, new_text)

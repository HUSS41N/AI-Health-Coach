from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from chat.schemas import ChatStreamRequest, FeedbackBody
from chat.service import run_chat_stream
from config import get_settings
from db.models import Message
from db.session import get_db, get_session_factory
from guardrails.input_validation import prepare_user_message
from guardrails.rate_limiter import check_duplicate_message, check_rate_limit
from memory.tasks import run_post_chat_memory_work
from redis_client import inflight_release, inflight_try_acquire, stable_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages")
def list_messages(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[str | None, Query()] = None,
    before_id: Annotated[int | None, Query()] = None,
    limit: int = Query(30, ge=1, le=100),
):
    settings = get_settings()
    uid = user_id or settings.default_user_id
    stmt = select(Message).where(Message.user_id == uid)
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    stmt = stmt.order_by(Message.created_at.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows_chrono = list(reversed(rows))
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "user_feedback": m.user_feedback,
            }
            for m in rows_chrono
        ],
        "has_more": has_more,
    }


@router.get("/messages/search")
def search_messages(
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(..., min_length=2, max_length=200),
    user_id: Annotated[str | None, Query()] = None,
    limit: int = Query(30, ge=1, le=100),
):
    """Substring search in the current user's messages (newest first)."""
    settings = get_settings()
    uid = user_id or settings.default_user_id
    needle = "".join(c for c in q.strip() if c not in "%_\\")[:200]
    if len(needle) < 2:
        return {"matches": []}
    pattern = f"%{needle}%"
    stmt = (
        select(Message)
        .where(Message.user_id == uid, Message.content.ilike(pattern))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    return {
        "matches": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ],
    }


@router.post("/stream")
def chat_stream(req: ChatStreamRequest, background_tasks: BackgroundTasks):
    settings = get_settings()
    uid = (req.user_id or settings.default_user_id).strip() or settings.default_user_id
    if not (req.content or "").strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    if not check_rate_limit(uid):
        raise HTTPException(
            status_code=429,
            detail="You're sending messages too quickly. Please slow down.",
        )

    prep = prepare_user_message(
        req.content,
        max_length=settings.guardrail_max_message_chars,
    )
    dup_src = prep.pipeline_text if not prep.rejected else prep.storage_text
    dup_key = stable_hash(dup_src) if dup_src.strip() else stable_hash("empty")
    if not check_duplicate_message(uid, dup_key):
        raise HTTPException(
            status_code=429,
            detail="Duplicate message; please wait a moment.",
        )

    if not inflight_try_acquire(uid, req.client_request_id or ""):
        raise HTTPException(
            status_code=409,
            detail="Duplicate in-flight request for this client_request_id",
        )

    factory = get_session_factory()
    session = factory()
    capture: dict[str, str] = {}

    def event_gen():
        committed = False
        try:
            for chunk in run_chat_stream(
                session,
                user_id=uid,
                prepared=prep,
                capture=capture,
            ):
                yield chunk
            session.commit()
            committed = True
        except Exception:
            session.rollback()
            logger.exception("chat stream transaction failed")
            raise
        finally:
            session.close()
            inflight_release(uid, req.client_request_id or "")
            if committed and not capture.get("skip_memory"):
                background_tasks.add_task(
                    run_post_chat_memory_work,
                    uid,
                    capture.get("user_message", prep.storage_text),
                    capture.get("assistant_text", ""),
                )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.patch("/messages/{message_id}/feedback")
def set_feedback(
    message_id: int,
    body: FeedbackBody,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[str | None, Query()] = None,
):
    settings = get_settings()
    uid = user_id or settings.default_user_id
    msg = db.get(Message, message_id)
    if not msg or msg.user_id != uid:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.user_feedback = "up" if body.vote == "up" else "down"
    return {"ok": True, "message_id": message_id, "user_feedback": msg.user_feedback}

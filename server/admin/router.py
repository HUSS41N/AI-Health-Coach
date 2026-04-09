from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from admin.schemas import PromptUpdateBody
from db.models import (
    AgentPrompt,
    ConversationSummary,
    EpisodicMemory,
    Message,
    MemoryRow,
    User,
    UserMemory,
)
from db.session import get_db
from memory.long_term import load_profile_db
from memory.summary import load_summary_db
from prompts.service import list_prompt_rows, upsert_prompt

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(db: Annotated[Session, Depends(get_db)]):
    parts: set[str] = set()
    parts.update(db.scalars(select(User.user_id)).all())
    parts.update(db.scalars(select(Message.user_id).distinct()).all())
    parts.update(db.scalars(select(UserMemory.user_id)).all())
    parts.update(db.scalars(select(EpisodicMemory.user_id).distinct()).all())
    parts.update(db.scalars(select(ConversationSummary.user_id)).all())
    parts.update(db.scalars(select(MemoryRow.user_id).distinct()).all())
    return {"users": sorted(parts)}


@router.get("/users/{user_id}/overview")
def user_overview(user_id: str, db: Annotated[Session, Depends(get_db)]):
    profile = load_profile_db(db, user_id)
    summary = load_summary_db(db, user_id)

    episodic_rows = list(
        db.scalars(
            select(EpisodicMemory)
            .where(EpisodicMemory.user_id == user_id)
            .order_by(EpisodicMemory.created_at.desc())
            .limit(50)
        ).all()
    )

    legacy_rows = list(
        db.scalars(
            select(MemoryRow)
            .where(MemoryRow.user_id == user_id)
            .order_by(MemoryRow.created_at.desc())
            .limit(50)
        ).all()
    )

    msg_count = db.scalar(
        select(func.count()).select_from(Message).where(Message.user_id == user_id)
    )
    recent = list(
        db.scalars(
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(80)
        ).all()
    )
    recent_chrono = list(reversed(recent))

    return {
        "user_id": user_id,
        "profile": profile,
        "summary": summary,
        "episodic": [
            {
                "id": r.id,
                "content": r.content,
                "tags": list(r.tags or []),
                "created_at": r.created_at.isoformat(),
            }
            for r in episodic_rows
        ],
        "legacy_memory_rows": [
            {
                "id": r.id,
                "type": r.type,
                "content": r.content,
                "created_at": r.created_at.isoformat(),
            }
            for r in legacy_rows
        ],
        "message_count": int(msg_count or 0),
        "recent_messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "user_feedback": m.user_feedback,
            }
            for m in recent_chrono
        ],
    }


@router.get("/prompts")
def list_prompts(db: Annotated[Session, Depends(get_db)]):
    rows = list_prompt_rows(db)
    return {
        "prompts": [
            {
                "key": r.key,
                "title": r.title,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.get("/prompts/{prompt_key}")
def get_prompt(prompt_key: str, db: Annotated[Session, Depends(get_db)]):
    row = db.get(AgentPrompt, prompt_key)
    if not row:
        raise HTTPException(status_code=404, detail="Unknown prompt key")
    return {
        "key": row.key,
        "title": row.title,
        "content": row.content,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.patch("/prompts/{prompt_key}")
def update_prompt(
    prompt_key: str,
    body: PromptUpdateBody,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        upsert_prompt(db, prompt_key, body.content)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    row = db.get(AgentPrompt, prompt_key)
    return {
        "ok": True,
        "key": row.key if row else prompt_key,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }

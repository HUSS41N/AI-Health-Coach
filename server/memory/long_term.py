from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import MemoryRow, UserMemory
from llm.client import complete_json_chat
from memory.schemas import LongTermExtracted
from prompts.service import get_prompt_content

logger = logging.getLogger(__name__)


def extract_long_term_memory(message: str) -> dict[str, Any]:
    if not (message or "").strip():
        return {}
    try:
        system = get_prompt_content("long_term_profile")
        data, _ = complete_json_chat(
            system,
            f'User message:\n"""{message.strip()[:4000]}"""',
        )
        validated = LongTermExtracted.model_validate(data)
        return validated.model_dump(exclude_none=True)
    except Exception as e:
        logger.warning("extract_long_term_memory failed: %s", e)
        return {}


def merge_profile(old_profile: dict[str, Any], new_data: dict[str, Any]) -> dict[str, Any]:
    """Do not overwrite with null/empty; union arrays."""
    out = dict(old_profile)
    list_keys = ("goals", "conditions", "preferences")
    scalar_keys = ("age", "gender", "name", "lifestyle")

    for key in scalar_keys:
        if key not in new_data:
            continue
        val = new_data[key]
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        out[key] = val

    for key in list_keys:
        if key not in new_data:
            continue
        raw = new_data[key]
        if raw is None:
            continue
        if not isinstance(raw, list):
            raw = [raw] if raw else []
        new_items = {str(x).strip() for x in raw if str(x).strip()}
        if not new_items:
            continue
        existing = set(out.get(key) or [])
        if not isinstance(existing, set):
            existing = {str(x) for x in existing if x}
        existing |= new_items
        out[key] = sorted(existing)

    return out


def _default_profile() -> dict[str, Any]:
    return {
        "age": None,
        "gender": None,
        "goals": [],
        "conditions": [],
        "preferences": [],
        "name": None,
        "lifestyle": None,
    }


def load_profile_db(session: Session, user_id: str) -> dict[str, Any]:
    row = session.get(UserMemory, user_id)
    if row and row.profile:
        merged = _default_profile()
        merged.update(row.profile)
        return merged
    # one-time read from legacy memory.profile row
    legacy = session.scalars(
        select(MemoryRow)
        .where(MemoryRow.user_id == user_id, MemoryRow.type == "profile")
        .order_by(MemoryRow.id.desc())
        .limit(1)
    ).first()
    if legacy and isinstance(legacy.content, dict):
        merged = _default_profile()
        merged.update(legacy.content)
        return merged
    return _default_profile()


def upsert_user_memory(session: Session, user_id: str, profile: dict[str, Any]) -> None:
    row = session.get(UserMemory, user_id)
    now = datetime.now(timezone.utc)
    if row:
        row.profile = profile
        row.updated_at = now
    else:
        session.add(
            UserMemory(user_id=user_id, profile=profile, updated_at=now),
        )


def apply_long_term_from_message(session: Session, user_id: str, message: str) -> None:
    new_json = extract_long_term_memory(message)
    if not new_json:
        return
    if not any(
        new_json.get(k) not in (None, [], "")
        for k in (
            "age",
            "gender",
            "name",
            "goals",
            "conditions",
            "preferences",
            "lifestyle",
        )
    ):
        return
    old = load_profile_db(session, user_id)
    merged = merge_profile(old, new_json)
    upsert_user_memory(session, user_id, merged)

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import EpisodicMemory

_SYMPTOM_KW = {
    "fever",
    "pain",
    "headache",
    "anxiety",
    "anxious",
    "tired",
    "fatigue",
    "nausea",
    "cough",
    "dizzy",
    "chills",
    "migraine",
    "ache",
    "sore",
    "rash",
    "vomit",
    "diarrhea",
    "shortness",
    "breath",
}
_HABIT_KW = {
    "gym",
    "workout",
    "exercise",
    "diet",
    "sleep",
    "eating",
    "water",
    "running",
    "walking",
    "yoga",
    "meditation",
}
_EMOTION_KW = {
    "stress",
    "stressed",
    "anxious",
    "anxiety",
    "depressed",
    "sad",
    "worried",
    "overwhelmed",
    "panic",
    "lonely",
}
_TIME_PATTERNS = [
    (re.compile(r"\btoday\b", re.I), "today"),
    (re.compile(r"\byesterday\b", re.I), "yesterday"),
    (re.compile(r"\blast\s+week\b", re.I), "last_week"),
    (re.compile(r"\blast\s+month\b", re.I), "last_month"),
    (re.compile(r"\bthis\s+morning\b", re.I), "this_morning"),
    (re.compile(r"\btonight\b", re.I), "tonight"),
    (re.compile(r"\bfor\s+a\s+week\b", re.I), "duration_week"),
]


def should_store_episodic(message: str) -> bool:
    if not (message or "").strip():
        return False
    lower = message.lower()
    tokens = set(re.findall(r"[a-zA-Z]+", lower))
    if tokens & _SYMPTOM_KW:
        return True
    if tokens & _HABIT_KW:
        return True
    if tokens & _EMOTION_KW:
        return True
    for rx, _ in _TIME_PATTERNS:
        if rx.search(message):
            return True
    return False


def extract_tags(message: str) -> list[str]:
    """Keyword + time-phrase tags for overlap search (no embeddings)."""
    if not (message or "").strip():
        return []
    lower = message.lower()
    tags: set[str] = set()
    tokens = re.findall(r"[a-zA-Z]+", lower)
    for t in tokens:
        if len(t) < 3:
            continue
        if (
            t in _SYMPTOM_KW
            or t in _HABIT_KW
            or t in _EMOTION_KW
            or t in ("week", "month", "day", "night", "morning")
        ):
            tags.add(t)
    for rx, label in _TIME_PATTERNS:
        if rx.search(message):
            tags.add(label)
    # light stemming-ish: headache from head
    for phrase in ("headache", "migraine", "backpain", "stomach"):
        if phrase in lower.replace(" ", ""):
            tags.add(phrase)
    return sorted(tags)[:32]


def _normalize_content_snippet(content: str, max_len: int = 400) -> str:
    c = " ".join(content.split())
    return c[:max_len].strip().lower()


def episodic_duplicate_exists(session: Session, user_id: str, content: str) -> bool:
    snippet = _normalize_content_snippet(content)
    if len(snippet) < 12:
        return False
    rows = session.scalars(
        select(EpisodicMemory.content)
        .where(EpisodicMemory.user_id == user_id)
        .order_by(EpisodicMemory.created_at.desc())
        .limit(80)
    ).all()
    for existing in rows:
        if snippet in _normalize_content_snippet(existing):
            return True
        if _normalize_content_snippet(existing) in snippet and len(existing) > 20:
            return True
    return False


def store_episodic_memory(
    session: Session,
    user_id: str,
    content: str,
    *,
    max_content_len: int = 4000,
) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    if len(text) > max_content_len:
        text = text[: max_content_len - 20] + "\n…(truncated)"
    if not should_store_episodic(text):
        return False
    if episodic_duplicate_exists(session, user_id, text):
        return False
    tags = extract_tags(text)
    if not tags:
        tags = ["general"]
    session.add(
        EpisodicMemory(
            user_id=user_id,
            content=text,
            tags=tags,
        )
    )
    return True

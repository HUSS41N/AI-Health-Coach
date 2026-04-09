from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agents.schemas import ChoiceItem, QuestionAgentOutput
from db.models import OnboardingProgress, User
from memory.long_term import load_profile_db, merge_profile, upsert_user_memory
from redis_client import profile_cache_delete

logger = logging.getLogger(__name__)

STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"

STEP_GOAL = "goal"
STEP_CONDITIONS = "conditions"
STEP_LIFESTYLE = "lifestyle"

GREETINGS = frozenset(
    {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "yo", "hiya"},
)

GOAL_CHOICES: list[ChoiceItem] = [
    ChoiceItem(id="og_lose", label="Lose weight"),
    ChoiceItem(id="og_fit", label="Build strength & fitness"),
    ChoiceItem(id="og_sleep", label="Sleep better"),
    ChoiceItem(id="og_stress", label="Stress or mood"),
    ChoiceItem(id="og_eat", label="Healthier eating"),
    ChoiceItem(id="og_energy", label="More energy"),
]

CONDITION_CHOICES: list[ChoiceItem] = [
    ChoiceItem(id="oc_none", label="None"),
    ChoiceItem(id="oc_dm", label="Diabetes"),
    ChoiceItem(id="oc_bp", label="High blood pressure"),
    ChoiceItem(id="oc_heart", label="Heart or circulation"),
    ChoiceItem(id="oc_mental", label="Mental health (e.g. anxiety/depression)"),
    ChoiceItem(id="oc_other", label="Other (describe in a message)"),
]

LIFESTYLE_CHOICES: list[ChoiceItem] = [
    ChoiceItem(id="ol_desk", label="Mostly desk / low activity"),
    ChoiceItem(id="ol_light", label="Light movement most days"),
    ChoiceItem(id="ol_mod", label="Regular exercise (about 3+ days/week)"),
    ChoiceItem(id="ol_high", label="Very active / athletic"),
    ChoiceItem(id="ol_skip", label="Prefer not to say"),
]


def ensure_coach_user(session: Session, user_id: str) -> None:
    """Create users + onboarding_progress rows if missing."""
    row = session.get(User, user_id)
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(
            User(
                user_id=user_id,
                onboarding_status=STATUS_NOT_STARTED,
                created_at=now,
                updated_at=now,
            ),
        )
        session.flush()
        session.add(
            OnboardingProgress(user_id=user_id, collected_fields={}, updated_at=now),
        )
        session.flush()
        return
    prog = session.get(OnboardingProgress, user_id)
    if prog is None:
        session.add(
            OnboardingProgress(user_id=user_id, collected_fields={}, updated_at=now),
        )
        session.flush()


def get_onboarding_status(session: Session, user_id: str) -> str:
    u = session.get(User, user_id)
    if not u:
        return STATUS_NOT_STARTED
    return (u.onboarding_status or STATUS_NOT_STARTED).strip() or STATUS_NOT_STARTED


def onboarding_should_run(
    session: Session,
    user_id: str,
    *,
    intent_intent: str,
    protocol_name: str,
) -> bool:
    if get_onboarding_status(session, user_id) == STATUS_COMPLETED:
        return False
    if intent_intent == "emergency" or protocol_name == "emergency":
        logger.info("onboarding: skipped for emergency routing user_id=%s", user_id)
        return False
    return True


def get_onboarding_meta(session: Session, user_id: str) -> dict[str, Any]:
    st = get_onboarding_status(session, user_id)
    return {
        "active": st != STATUS_COMPLETED,
        "status": st,
    }


def _conditions_slot_filled(collected: dict[str, Any]) -> bool:
    c = collected.get("conditions")
    return isinstance(c, list) and len(c) > 0


def _normalize_selection(msg: str) -> str:
    m = msg.strip()
    if m.lower().startswith("selected:"):
        return m.split(":", 1)[1].strip()
    return m


def _current_step(collected: dict[str, Any]) -> str:
    if not (collected.get("goal") or "").strip():
        return STEP_GOAL
    if not _conditions_slot_filled(collected):
        return STEP_CONDITIONS
    if not (collected.get("lifestyle") or "").strip():
        return STEP_LIFESTYLE
    return "done"


def _apply_static_answer(
    collected: dict[str, Any],
    step: str,
    user_message: str,
) -> dict[str, Any]:
    out = dict(collected)
    norm = _normalize_selection(user_message)
    if not norm:
        return out
    low = norm.lower()

    if step == STEP_GOAL:
        if low in GREETINGS:
            return out
        out["goal"] = norm[:200]
        return out

    if step == STEP_CONDITIONS:
        if low in ("none", "no", "n/a", "not applicable", "no health conditions"):
            out["conditions"] = ["none"]
            return out
        if low == "other (describe in a message)":
            return out
        out["conditions"] = [norm[:120]]
        return out

    if step == STEP_LIFESTYLE:
        if low in ("prefer not to say", "pass", "skip", "n/a"):
            out["lifestyle"] = "Not specified"
        else:
            out["lifestyle"] = norm[:500]
        return out

    return out


def _collected_sufficient(collected: dict[str, Any]) -> bool:
    if not (collected.get("goal") or "").strip():
        return False
    if not (collected.get("lifestyle") or "").strip():
        return False
    conds = collected.get("conditions")
    return isinstance(conds, list) and len(conds) > 0


def _flush_collected_to_profile(session: Session, user_id: str, collected: dict[str, Any]) -> None:
    profile = load_profile_db(session, user_id)
    patch: dict[str, Any] = {}
    g = collected.get("goal")
    if g and str(g).strip():
        patch["goals"] = [str(g).strip()]
    conds = collected.get("conditions")
    if isinstance(conds, list) and conds:
        patch["conditions"] = [
            str(c).strip()
            for c in conds
            if str(c).strip() and str(c).strip().lower() != "none"
        ]
    life = collected.get("lifestyle")
    if life and str(life).strip():
        patch["lifestyle"] = str(life).strip()
    merged = merge_profile(profile, patch)
    upsert_user_memory(session, user_id, merged)


def apply_onboarding_turn(
    session: Session,
    user_id: str,
    user_message: str,
    profile: dict[str, Any],
) -> tuple[str, QuestionAgentOutput]:
    """
    Fast deterministic onboarding: fixed questions and tap choices (no LLM).
    `profile` is unused; kept for call-site compatibility.
    """
    _ = profile
    ensure_coach_user(session, user_id)
    prog = session.get(OnboardingProgress, user_id)
    if not prog:
        raise RuntimeError("onboarding_progress missing after ensure_coach_user")

    collected = dict(prog.collected_fields or {})
    step_before = _current_step(collected)

    if step_before != "done":
        collected = _apply_static_answer(collected, step_before, user_message)

    prog.collected_fields = collected
    prog.updated_at = datetime.now(timezone.utc)

    user = session.get(User, user_id)
    assert user is not None
    if user.onboarding_status == STATUS_NOT_STARTED:
        user.onboarding_status = STATUS_IN_PROGRESS
        user.updated_at = datetime.now(timezone.utc)

    empty_ui = QuestionAgentOutput()

    if _collected_sufficient(collected):
        user.onboarding_status = STATUS_COMPLETED
        user.updated_at = datetime.now(timezone.utc)
        _flush_collected_to_profile(session, user_id, collected)
        profile_cache_delete(user_id)
        logger.info("onboarding: completed (static) user_id=%s", user_id)
        return (
            "You're all set. Ask me anything about sleep, movement, nutrition, or "
            "stress — or tell me how your day went.",
            empty_ui,
        )

    step_after = _current_step(collected)
    if step_after == STEP_GOAL:
        return (
            "Let's start with what you want to focus on.",
            QuestionAgentOutput(
                interaction="choices",
                prompt="Pick one, or type your own goal below.",
                choices=list(GOAL_CHOICES),
            ),
        )
    if step_after == STEP_CONDITIONS:
        return (
            "Thanks. Next, anything medical we should keep in mind?",
            QuestionAgentOutput(
                interaction="choices",
                prompt="Tap an option or type a short note.",
                choices=list(CONDITION_CHOICES),
            ),
        )
    if step_after == STEP_LIFESTYLE:
        return (
            "Last one for now: how active is your typical week?",
            QuestionAgentOutput(
                interaction="choices",
                prompt="Tap what fits best — you can add detail in a message.",
                choices=list(LIFESTYLE_CHOICES),
            ),
        )
    return ("Thanks — let's continue.", empty_ui)

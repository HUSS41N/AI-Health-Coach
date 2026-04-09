from __future__ import annotations

import json
import logging
from typing import Any

from agents.schemas import OnboardingAgentOutput, OnboardingExtracted
from llm.client import complete_json_chat
from prompts.service import get_prompt_content

logger = logging.getLogger(__name__)


def _fallback_onboarding_output(
    collected_fields: dict[str, Any],
) -> OnboardingAgentOutput:
    """If JSON/LLM fails, continue from saved state instead of restarting at goal."""
    goal = (collected_fields.get("goal") or "").strip()
    life = (collected_fields.get("lifestyle") or "").strip()
    conds = collected_fields.get("conditions")
    conds_ok = isinstance(conds, list) and len(conds) > 0

    if goal and life and conds_ok:
        return OnboardingAgentOutput(
            response="Thanks — I've saved your preferences.",
            next_question="",
            extracted=OnboardingExtracted(),
            is_complete=True,
        )
    if not goal:
        return OnboardingAgentOutput(
            response="I'd like to learn what you're working toward.",
            next_question="What's your main health or wellness goal?",
            extracted=OnboardingExtracted(),
            is_complete=False,
        )
    if not conds_ok:
        return OnboardingAgentOutput(
            response="Thanks for sharing your goal.",
            next_question='Any health conditions or medications to know about? Say "none" if not.',
            extracted=OnboardingExtracted(),
            is_complete=False,
        )
    return OnboardingAgentOutput(
        response="Got it.",
        next_question="In a sentence or two, what does a typical day look like—work, movement, sleep, meals?",
        extracted=OnboardingExtracted(),
        is_complete=False,
    )


def run_onboarding_agent(
    *,
    user_message: str,
    existing_profile: dict[str, Any],
    collected_fields: dict[str, Any],
) -> OnboardingAgentOutput:
    """
    Conversational onboarding: one question at a time, extract structured fields.
    """
    system = get_prompt_content("onboarding_agent")
    payload = {
        "user_message": user_message,
        "existing_profile": existing_profile,
        "collected_fields": collected_fields,
    }
    user = (
        "Continue the onboarding conversation. Input JSON context:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        data, prov = complete_json_chat(system, user)
        if prov == "none" and not data:
            raise ValueError("no provider")
        out = OnboardingAgentOutput.model_validate(data)
        logger.debug("onboarding agent (%s): %s", prov, out.model_dump())
        return out
    except Exception as e:
        logger.warning("onboarding agent failed: %s", e)
        return _fallback_onboarding_output(collected_fields)

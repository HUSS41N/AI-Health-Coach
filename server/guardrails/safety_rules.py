from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_EMERGENCY = re.compile(
    r"\b(chest\s+pain|difficulty\s+breathing|shortness\s+of\s+breath|"
    r"can'?t\s+breathe|unconscious|severe\s+bleeding)\b",
    re.I,
)
_SELF_HARM = re.compile(
    r"\b(kill\s+myself|suicide|suicidal|hurt\s+myself|end\s+my\s+life)\b",
    re.I,
)
_MEDICATION = re.compile(
    r"\b(prescribe|prescription|dosage|dose\s+of|how\s+much\s+.*\s+(mg|ml|mcg))\b",
    re.I,
)

_RESPONSE_EMERGENCY = (
    "This could be serious. Please seek immediate medical attention "
    "or visit the nearest hospital."
)
_RESPONSE_SELF_HARM = (
    "I'm really sorry you're feeling this way. You're not alone. "
    "Please consider reaching out to a trusted person or a mental health professional."
)
_RESPONSE_MEDICATION = (
    "I can't prescribe medication, but I can share general health guidance."
)


def check_safety(message: str) -> dict:
    """
    Keyword-based safety triage. Returns dict:
    type: emergency | self_harm | medication | normal
    override: if True, skip LLM and return `response` as assistant text
    response: safe canned text when override
    """
    if not (message or "").strip():
        return {"type": "normal", "override": False, "response": ""}

    text = message.strip()

    if _EMERGENCY.search(text):
        logger.warning("guardrails: safety trigger=emergency")
        return {
            "type": "emergency",
            "override": True,
            "response": _RESPONSE_EMERGENCY,
        }
    if _SELF_HARM.search(text):
        logger.warning("guardrails: safety trigger=self_harm")
        return {
            "type": "self_harm",
            "override": True,
            "response": _RESPONSE_SELF_HARM,
        }
    if _MEDICATION.search(text):
        logger.warning("guardrails: safety trigger=medication")
        return {
            "type": "medication",
            "override": True,
            "response": _RESPONSE_MEDICATION,
        }

    return {"type": "normal", "override": False, "response": ""}

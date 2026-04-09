import json

from agents.schemas import IntentOutput
from protocol.engine import ProtocolOutput


def _personalization_block(profile: dict) -> str:
    """Coach copy when onboarding (or profile) has goal / conditions / lifestyle."""
    goals = profile.get("goals") or []
    conditions = profile.get("conditions") or []
    life = profile.get("lifestyle")
    if not goals and not conditions and not (life and str(life).strip()):
        return ""
    lines = ["\nYou are a health coach helping a user with:"]
    if goals:
        lines.append(f"* Goal: {', '.join(str(g) for g in goals[:6])}")
    if conditions:
        lines.append(f"* Conditions: {', '.join(str(c) for c in conditions[:10])}")
    if life and str(life).strip():
        lines.append(f"* Lifestyle: {str(life).strip()}")
    return "\n".join(lines) + "\n"


def build_system_prompt(
    preamble: str,
    profile: dict,
    summary: str | None,
    episodic: list[str],
    intent: IntentOutput,
    protocol: ProtocolOutput,
) -> str:
    parts = [
        (preamble or "").strip()
        or "You are a safe AI health coach. Be concise and supportive.",
    ]
    pers = _personalization_block(profile)
    if pers:
        parts.append(pers)
    parts.append(
        f"\nUser profile (structured): {json.dumps(profile, ensure_ascii=False)}",
    )
    if profile.get("name"):
        parts.append(
            f"\nUse the user's preferred name naturally when it fits: {profile['name']}."
        )
    if summary:
        parts.append(f"\nConversation summary:\n{summary}")
    if episodic:
        parts.append("\nNotable past facts:\n- " + "\n- ".join(episodic))
    parts.append(
        f'\nClassifier intent: {intent.intent} (urgency {intent.urgency}). '
        f'Entities: {", ".join(intent.entities) or "none"}.'
    )
    parts.append(
        f"\nClinical routing hint ({protocol.protocol}, priority {protocol.priority}):\n"
        f"{protocol.response_hint}"
    )
    parts.append(
        "\nRespond with supportive coaching only. "
        "If emergency protocol applies, prioritize urgent safety guidance first."
    )
    return "".join(parts)

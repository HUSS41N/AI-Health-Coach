import re
from pydantic import BaseModel, Field


class ProtocolOutput(BaseModel):
    protocol: str = Field(
        ...,
        description="Rule id applied, e.g. emergency, fever, general",
    )
    response_hint: str = Field(..., description="Guidance for the response LLM")
    priority: str = Field(..., description="low | medium | high")


class ProtocolEngine:
    """Rule-based safety and triage layer (no LLM)."""

    _severe = re.compile(
        r"\b(chest\s+pain|can't\s+breathe|cannot\s+breathe|suicid|"
        r"stroke|heart\s+attack|unconscious|severe\s+blood)\b",
        re.I,
    )
    _fever = re.compile(r"\b(fever|temperature|febrile|chills)\b", re.I)
    _chest = re.compile(r"\b(chest\s+pain|pressure\s+on\s+chest)\b", re.I)
    _headache = re.compile(r"\b(headache|migraine)\b", re.I)

    def run(self, user_message: str, entities: list[str]) -> ProtocolOutput:
        text = user_message.lower()
        blob = " ".join([text, *[e.lower() for e in entities]])

        if self._severe.search(blob) or self._chest.search(blob):
            return ProtocolOutput(
                protocol="emergency",
                response_hint=(
                    "Urgently advise calling local emergency services or going to ER now. "
                    "Do not diagnose. Do not minimize. No home remedies for possible emergencies."
                ),
                priority="high",
            )

        if self._fever.search(blob):
            return ProtocolOutput(
                protocol="fever",
                response_hint=(
                    "Ask how long symptoms lasted and if there are red flags. "
                    "Suggest hydration/rest. Encourage clinician if high fever persists or worsens."
                ),
                priority="medium",
            )

        if self._headache.search(blob):
            return ProtocolOutput(
                protocol="headache",
                response_hint=(
                    "Show empathy; ask onset, severity, neurological red flags. "
                    "Suggest medical evaluation for sudden severe headache or neuro symptoms."
                ),
                priority="medium",
            )

        return ProtocolOutput(
            protocol="general",
            response_hint=(
                "Supportive coaching only: no diagnosis or prescriptions. "
                "Encourage professional care for serious or persistent issues."
            ),
            priority="low",
        )

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class IntentOutput(BaseModel):
    intent: Literal["health_query", "casual", "emergency", "onboarding"] = Field(
        ...,
    )
    entities: list[str] = Field(default_factory=list)
    urgency: Literal["low", "medium", "high"] = Field(...)


class ProfilePatch(BaseModel):
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    goals: list[str] | None = None
    conditions: list[str] | None = None
    preferences: list[str] | None = None


class MemoryExtractionOutput(BaseModel):
    update_profile: ProfilePatch | None = None
    store_memory: list[str] = Field(default_factory=list)


class ResponseAgentOutput(BaseModel):
    response: str
    tone: str = "empathetic"
    follow_up_questions: list[str] = Field(default_factory=list)


class ScaleConfig(BaseModel):
    id: str = "severity"
    min: int = 0
    max: int = 10
    step: int = 1
    label_low: str = "Low"
    label_high: str = "High"
    title: str = "How much?"


class ChoiceItem(BaseModel):
    id: str
    label: str


class OnboardingExtracted(BaseModel):
    goal: str | None = None
    # None = not provided this turn (do not merge). Use ["none"] when user has no conditions.
    conditions: list[str] | None = None
    lifestyle: str | None = None


class OnboardingAgentOutput(BaseModel):
    response: str = ""
    next_question: str = ""
    extracted: OnboardingExtracted = Field(default_factory=OnboardingExtracted)
    is_complete: bool = False

    model_config = {"extra": "ignore"}

    @field_validator("extracted", mode="before")
    @classmethod
    def _coerce_extracted(cls, v: Any) -> Any:
        if v is None:
            return OnboardingExtracted()
        if isinstance(v, dict):
            return OnboardingExtracted.model_validate(v)
        return v


class QuestionAgentOutput(BaseModel):
    """Structured UI hints: scales (anxiety/fever) or tap-to-reply choices."""

    interaction: Literal["none", "scale", "choices"] = "none"
    prompt: str = ""
    scale: ScaleConfig | None = None
    choices: list[ChoiceItem] = Field(default_factory=list)

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class LongTermExtracted(BaseModel):
    """Validated LLM output for profile fields (JSON-only contract)."""

    age: int | None = None
    gender: str | None = None
    goals: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    name: str | None = Field(
        default=None,
        description="Optional display name if user states it",
    )

    @field_validator("goals", "conditions", "preferences", mode="before")
    @classmethod
    def listify(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return [str(v).strip()] if str(v).strip() else []


class MemoryContext(BaseModel):
    recent_messages: list[dict[str, Any]]
    summary: str | None
    profile: dict[str, Any]
    episodic: list[str]

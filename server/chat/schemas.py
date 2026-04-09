from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatStreamRequest(BaseModel):
    user_id: str | None = Field(
        default=None,
        description="Stable user id; defaults to server default_user_id",
    )
    content: str = Field(..., min_length=1)
    client_request_id: str | None = Field(
        default=None,
        description="Optional idempotency key for in-flight deduplication",
    )

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v


class FeedbackBody(BaseModel):
    vote: Literal["up", "down"]

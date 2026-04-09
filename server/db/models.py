from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    user_feedback: Mapped[str | None] = mapped_column(String(16), nullable=True)


class MemoryRow(Base):
    """Legacy unified memory table (optional reads for migration)."""

    __tablename__ = "memory"
    __table_args__ = (Index("ix_memory_user_type", "user_id", "type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[str] = mapped_column(String(32))
    content: Mapped[dict] = mapped_column(JSONB)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class User(Base):
    """App user row (client-generated user_id); onboarding gating."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    onboarding_status: Mapped[str] = mapped_column(
        String(32),
        server_default=text("'NOT_STARTED'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"

    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    collected_fields: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserMemory(Base):
    __tablename__ = "user_memory"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class EpisodicMemory(Base):
    __tablename__ = "episodic_memory"
    __table_args__ = (Index("ix_episodic_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text())
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        server_default=text("'{}'::varchar[]"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ConversationSummary(Base):
    __tablename__ = "conversation_summary"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    summary: Mapped[str] = mapped_column(Text(), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AgentPrompt(Base):
    """Editable LLM system prompts (managed via admin API)."""

    __tablename__ = "agent_prompts"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    content: Mapped[str] = mapped_column(Text(), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

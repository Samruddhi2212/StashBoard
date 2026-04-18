"""SQLAlchemy 2.0 declarative ORM models for Stashboard.

All models use mapped_column() / Mapped[] for full type-safety.
pgvector is imported conditionally so the codebase runs without it
(the embedding column degrades to Text for local development).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# pgvector is optional — install `pgvector` package + extension for production
try:
    from pgvector.sqlalchemy import Vector  # type: ignore

    _VectorType = Vector(384)
except ImportError:
    _VectorType = Text  # type: ignore  # fallback; embeddings won't be usable without pgvector


# ── Mixins ────────────────────────────────────────────────────────────────────


class TimestampMixin:
    """Adds auto-managed created_at / updated_at columns to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ── Models ────────────────────────────────────────────────────────────────────


class User(TimestampMixin, Base):
    """A registered Stashboard user.

    Supports both email/password and OAuth (Google) authentication.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    google_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
    )
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)

    # Relationships
    spaces: Mapped[List["Space"]] = relationship(
        "Space", back_populates="user", cascade="all, delete-orphan"
    )
    clips: Mapped[List["Clip"]] = relationship(
        "Clip", back_populates="user", cascade="all, delete-orphan"
    )
    snippets: Mapped[List["Snippet"]] = relationship(
        "Snippet", back_populates="user", cascade="all, delete-orphan"
    )
    todos: Mapped[List["Todo"]] = relationship(
        "Todo", back_populates="user", cascade="all, delete-orphan"
    )
    team_memberships: Mapped[List["TeamMember"]] = relationship(
        "TeamMember", back_populates="user"
    )


class Space(TimestampMixin, Base):
    """A named compartment for organizing clips (e.g. Work, Personal)."""

    __tablename__ = "spaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="📁", nullable=False)
    color: Mapped[Optional[str]] = mapped_column(
        String(7), nullable=True
    )  # Hex color, e.g. #6366F1
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="spaces")
    clips: Mapped[List["Clip"]] = relationship("Clip", back_populates="space")
    snippets: Mapped[List["Snippet"]] = relationship("Snippet", back_populates="space")


class Clip(TimestampMixin, Base):
    """A single clipboard capture — the core Stashboard data entity.

    Every copy event in the browser produces one Clip record.
    The embedding column stores a 384-dimensional sentence-transformer
    vector for semantic search (requires pgvector extension).
    """

    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    copy_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # 384-dim vector for all-MiniLM-L6-v2 embeddings; degrades to Text without pgvector
    embedding = mapped_column(_VectorType, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="clips")
    space: Mapped[Optional["Space"]] = relationship("Space", back_populates="clips")

    __table_args__ = (
        # Efficient listing by user, newest first
        Index("ix_clips_user_created", "user_id", "created_at"),
        # Efficient category filtering per user
        Index("ix_clips_user_category", "user_id", "category"),
        # Efficient pin filtering per user
        Index("ix_clips_user_pinned", "user_id", "pinned"),
    )


class Snippet(TimestampMixin, Base):
    """A curated, reusable text snippet with an optional keyboard shortcut.

    Snippets differ from Clips: they are intentionally created and persist
    indefinitely, whereas Clips are ephemeral captures.
    """

    __tablename__ = "snippets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    space_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    shortcut: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True
    )
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="snippets")
    space: Mapped[Optional["Space"]] = relationship("Space", back_populates="snippets")


class Todo(TimestampMixin, Base):
    """A todo item, optionally created from a Clip (e.g. copy a task and save it)."""

    __tablename__ = "todos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clip_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clips.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="todos")
    source_clip: Mapped[Optional["Clip"]] = relationship("Clip")


class Team(TimestampMixin, Base):
    """A team workspace for shared clips, spaces, and snippets (Phase 6)."""

    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    plan: Mapped[str] = mapped_column(
        String(20), default="team_starter", nullable=False
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Relationships
    owner: Mapped["User"] = relationship("User")
    members: Mapped[List["TeamMember"]] = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(TimestampMixin, Base):
    """Membership record linking a User to a Team with a role."""

    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Roles: owner | admin | member
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="team_memberships")

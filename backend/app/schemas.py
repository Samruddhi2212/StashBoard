"""Pydantic v2 schemas for all Stashboard API request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Shared base ───────────────────────────────────────────────────────────────


class OrmBase(BaseModel):
    """Base model with ORM mode enabled for SQLAlchemy compatibility."""

    model_config = ConfigDict(from_attributes=True)


# ── User schemas ──────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Payload for registering a new user with email/password."""

    email: str = Field(..., max_length=255, examples=["user@example.com"])
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)


class UserResponse(OrmBase):
    """Public user representation returned by the API."""

    id: uuid.UUID
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    plan: str
    is_verified: bool
    created_at: datetime


# ── Space schemas ─────────────────────────────────────────────────────────────


class SpaceCreate(BaseModel):
    """Payload for creating a new space."""

    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="📁", max_length=10)
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class SpaceUpdate(BaseModel):
    """Partial payload for updating an existing space."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    icon: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class SpaceResponse(OrmBase):
    """Space representation returned by the API."""

    id: uuid.UUID
    name: str
    icon: str
    color: Optional[str]
    is_default: bool
    sort_order: int
    created_at: datetime


# ── Clip schemas ──────────────────────────────────────────────────────────────


class ClipCreate(BaseModel):
    """Payload for creating a new clip (typically sent by the extension during sync)."""

    text: str = Field(..., min_length=1)
    category: str = Field(default="text", max_length=20)
    source_url: Optional[str] = Field(None, max_length=2048)
    source_title: Optional[str] = Field(None, max_length=500)
    space_id: Optional[uuid.UUID] = None
    pinned: bool = False
    copy_count: int = Field(default=1, ge=1)
    tags: List[str] = Field(default_factory=list)
    # Client-side timestamp (ms since epoch); server normalizes to datetime
    client_timestamp: Optional[int] = Field(None, description="Unix ms timestamp from client")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {
            "email", "phone", "url", "address", "code",
            "color_hex", "json", "ip_address", "text",
        }
        return v if v in allowed else "text"


class ClipUpdate(BaseModel):
    """Partial payload for updating a clip."""

    text: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, max_length=20)
    space_id: Optional[uuid.UUID] = None
    pinned: Optional[bool] = None
    tags: Optional[List[str]] = None


class ClipResponse(OrmBase):
    """Full clip representation returned by the API."""

    id: uuid.UUID
    user_id: uuid.UUID
    space_id: Optional[uuid.UUID]
    text: str
    category: str
    source_url: Optional[str]
    source_title: Optional[str]
    pinned: bool
    copy_count: int
    is_sensitive: bool
    tags: List[Any]
    created_at: datetime
    updated_at: datetime


class ClipListResponse(BaseModel):
    """Paginated list of clips."""

    clips: List[ClipResponse]
    total: int
    offset: int
    limit: int


class ClipSearchQuery(BaseModel):
    """Parameters for searching clips."""

    query: str = Field(..., min_length=1, max_length=500)
    space_id: Optional[uuid.UUID] = None
    category: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    semantic: bool = Field(
        default=False,
        description="Use semantic (vector) search instead of full-text search",
    )


# ── Sync schemas ──────────────────────────────────────────────────────────────


class SyncClip(BaseModel):
    """A single clip entry in a batch sync request from the extension."""

    client_id: str = Field(..., description="The UUID generated client-side by the extension")
    text: str = Field(..., min_length=1)
    category: str = Field(default="text", max_length=20)
    source_url: Optional[str] = Field(None, max_length=2048)
    source_title: Optional[str] = Field(None, max_length=500)
    pinned: bool = False
    copy_count: int = Field(default=1, ge=1)
    tags: List[str] = Field(default_factory=list)
    timestamp: int = Field(..., description="Unix ms timestamp")


class SyncBatchRequest(BaseModel):
    """Batch sync request sent by the extension to push local clips to the server.

    The extension collects all clips created since the last_sync_at watermark
    and sends them in a single request.
    """

    clips: List[SyncClip] = Field(..., max_length=500)
    last_sync_at: Optional[int] = Field(
        None, description="Unix ms timestamp of last successful sync"
    )
    device_id: Optional[str] = Field(None, max_length=100)


class SyncBatchResponse(BaseModel):
    """Response to a batch sync, returning new clips from the server."""

    created: int = Field(description="Number of new clips written to the server")
    updated: int = Field(description="Number of existing clips updated (dedup)")
    server_clips: List[ClipResponse] = Field(
        description="Clips created on other devices since last_sync_at"
    )
    sync_timestamp: int = Field(description="Unix ms timestamp to use as next last_sync_at")


# ── Auth schemas ──────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """JWT access token returned after successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until expiry")
    user: UserResponse


class LoginRequest(BaseModel):
    """Email/password login payload."""

    email: str
    password: str

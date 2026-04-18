"""Clip CRUD + search API endpoints.

All routes require authentication (Phase 3 will add JWT middleware).
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    ClipCreate,
    ClipListResponse,
    ClipResponse,
    ClipSearchQuery,
    ClipUpdate,
)
from app.services.clip_service import ClipService

router = APIRouter()


# ── Helper ────────────────────────────────────────────────────────────────────

def get_clip_service(db: AsyncSession = Depends(get_db)) -> ClipService:
    """Dependency that injects a ClipService backed by the current DB session."""
    return ClipService(db)


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.post("/", response_model=ClipResponse, status_code=status.HTTP_201_CREATED)
async def create_clip(
    payload: ClipCreate,
    # TODO(Phase 3): replace hardcoded user_id with current_user from JWT
    user_id: uuid.UUID = Query(..., description="Authenticated user ID"),
    service: ClipService = Depends(get_clip_service),
) -> ClipResponse:
    """Creates a new clip and enqueues an embedding generation task."""
    return await service.create_clip(user_id=user_id, payload=payload)


@router.get("/", response_model=ClipListResponse)
async def list_clips(
    user_id: uuid.UUID = Query(...),
    space_id: Optional[uuid.UUID] = Query(None),
    category: Optional[str] = Query(None),
    pinned: Optional[bool] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=200),
    service: ClipService = Depends(get_clip_service),
) -> ClipListResponse:
    """Returns a paginated list of clips, newest first, pinned on top."""
    return await service.list_clips(
        user_id=user_id,
        space_id=space_id,
        category=category,
        pinned=pinned,
        offset=offset,
        limit=limit,
    )


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    service: ClipService = Depends(get_clip_service),
) -> ClipResponse:
    """Returns a single clip by ID."""
    clip = await service.get_clip(clip_id=clip_id, user_id=user_id)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip


@router.patch("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: uuid.UUID,
    payload: ClipUpdate,
    user_id: uuid.UUID = Query(...),
    service: ClipService = Depends(get_clip_service),
) -> ClipResponse:
    """Partially updates a clip (text, category, space, pin state, tags)."""
    clip = await service.update_clip(clip_id=clip_id, user_id=user_id, payload=payload)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip


@router.delete("/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(
    clip_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    service: ClipService = Depends(get_clip_service),
) -> None:
    """Permanently deletes a clip."""
    deleted = await service.delete_clip(clip_id=clip_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")


@router.post("/{clip_id}/pin", response_model=ClipResponse)
async def toggle_pin(
    clip_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    service: ClipService = Depends(get_clip_service),
) -> ClipResponse:
    """Toggles the pinned state of a clip."""
    clip = await service.toggle_pin(clip_id=clip_id, user_id=user_id)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip


# ── Search ────────────────────────────────────────────────────────────────────


@router.post("/search", response_model=ClipListResponse)
async def search_clips(
    query: ClipSearchQuery,
    user_id: uuid.UUID = Query(...),
    service: ClipService = Depends(get_clip_service),
) -> ClipListResponse:
    """Full-text search across clip text, source title, and source URL.

    Set `semantic=true` in the request body to use vector similarity search
    (requires pgvector and pre-computed embeddings — Phase 4).
    """
    return await service.search_clips(user_id=user_id, query=query)

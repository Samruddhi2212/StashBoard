"""Extension sync endpoint — bulk upsert clips from the Chrome extension.

Phase 3 feature: the extension calls POST /api/sync/batch periodically to
push locally captured clips to the server and pull clips from other devices.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Clip
from app.schemas import ClipResponse, SyncBatchRequest, SyncBatchResponse
from app.services.categorizer import classify

router = APIRouter()


@router.post("/batch", response_model=SyncBatchResponse)
async def sync_batch(
    payload: SyncBatchRequest,
    user_id: uuid.UUID = Query(..., description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
) -> SyncBatchResponse:
    """Bulk upserts clips from the extension and returns server-side changes.

    Algorithm:
    1. For each clip in the request, check if the client_id already exists.
       - If yes: update copy_count if higher, update timestamp if newer.
       - If no: check for text deduplication within the user's clips.
         If text matches, increment copy_count; otherwise create new record.
    2. Fetch all clips created on the server since last_sync_at (other devices).
    3. Return counts and the new server clips for the extension to merge locally.
    """
    created_count = 0
    updated_count = 0
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    for sync_clip in payload.clips:
        # Check by client_id first (idempotent re-sends)
        existing = await db.execute(
            select(Clip).where(
                Clip.user_id == user_id,
                Clip.id == uuid.UUID(sync_clip.client_id),
            )
        )
        clip = existing.scalar_one_or_none()

        if clip:
            if sync_clip.copy_count > clip.copy_count:
                clip.copy_count = sync_clip.copy_count
                updated_count += 1
        else:
            # Text deduplication
            dup = await db.execute(
                select(Clip).where(Clip.user_id == user_id, Clip.text == sync_clip.text)
            )
            dup_clip = dup.scalar_one_or_none()

            if dup_clip:
                dup_clip.copy_count = max(dup_clip.copy_count, sync_clip.copy_count) + 1
                updated_count += 1
            else:
                new_clip = Clip(
                    id=uuid.UUID(sync_clip.client_id),
                    user_id=user_id,
                    text=sync_clip.text,
                    category=sync_clip.category or classify(sync_clip.text),
                    source_url=sync_clip.source_url,
                    source_title=sync_clip.source_title,
                    pinned=sync_clip.pinned,
                    copy_count=sync_clip.copy_count,
                    tags=sync_clip.tags,
                )
                db.add(new_clip)
                created_count += 1

    await db.flush()

    # Fetch server clips added since last_sync_at (from other devices)
    server_clips: list[Clip] = []
    if payload.last_sync_at:
        last_sync_dt = datetime.fromtimestamp(payload.last_sync_at / 1000, tz=timezone.utc)
        result = await db.execute(
            select(Clip)
            .where(Clip.user_id == user_id, Clip.created_at > last_sync_dt)
            .order_by(Clip.created_at.desc())
            .limit(200)
        )
        server_clips = list(result.scalars().all())

    return SyncBatchResponse(
        created=created_count,
        updated=updated_count,
        server_clips=[ClipResponse.model_validate(c) for c in server_clips],
        sync_timestamp=now_ms,
    )

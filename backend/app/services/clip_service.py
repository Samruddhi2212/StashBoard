"""Business logic for Clip CRUD and search operations."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Clip
from app.schemas import (
    ClipCreate,
    ClipListResponse,
    ClipResponse,
    ClipSearchQuery,
    ClipUpdate,
)
from app.services.categorizer import classify
from app.services.search_service import semantic_search


class ClipService:
    """Encapsulates all data-access logic for Clip records.

    Args:
        db: An open AsyncSession to use for all queries within the request.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_clip(self, user_id: uuid.UUID, payload: ClipCreate) -> ClipResponse:
        """Creates a new clip, deduplicating by text within the user's corpus.

        If an identical text already exists, increments copy_count and returns
        the updated record rather than creating a duplicate.

        After persisting, enqueues an embedding generation task (Phase 4).

        Args:
            user_id: ID of the authenticated user.
            payload:  ClipCreate schema with clip data from the client.

        Returns:
            The created or updated ClipResponse.
        """
        # Text deduplication
        existing_result = await self._db.execute(
            select(Clip).where(Clip.user_id == user_id, Clip.text == payload.text)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.copy_count += 1
            if payload.source_url:
                existing.source_url = payload.source_url
            if payload.source_title:
                existing.source_title = payload.source_title
            await self._db.flush()
            await self._db.refresh(existing)
            return ClipResponse.model_validate(existing)

        # Infer category if not provided
        category = payload.category or classify(payload.text)

        clip = Clip(
            user_id=user_id,
            space_id=payload.space_id,
            text=payload.text,
            category=category,
            source_url=payload.source_url,
            source_title=payload.source_title,
            pinned=payload.pinned,
            copy_count=payload.copy_count,
            tags=payload.tags,
        )
        self._db.add(clip)
        await self._db.flush()
        await self._db.refresh(clip)

        # Phase 4: enqueue embedding generation
        # generate_embedding.delay(str(clip.id))

        return ClipResponse.model_validate(clip)

    async def list_clips(
        self,
        user_id: uuid.UUID,
        space_id: Optional[uuid.UUID] = None,
        category: Optional[str] = None,
        pinned: Optional[bool] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> ClipListResponse:
        """Returns a paginated, filtered list of clips sorted pinned-first then newest.

        Args:
            user_id:   Filter to this user's clips.
            space_id:  Optional space filter.
            category:  Optional category filter.
            pinned:    Optional pin state filter.
            offset:    Pagination offset.
            limit:     Maximum results to return.

        Returns:
            ClipListResponse with the page of clips and total count.
        """
        base_query = select(Clip).where(Clip.user_id == user_id)

        if space_id is not None:
            base_query = base_query.where(Clip.space_id == space_id)
        if category is not None:
            base_query = base_query.where(Clip.category == category)
        if pinned is not None:
            base_query = base_query.where(Clip.pinned == pinned)

        count_result = await self._db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        data_result = await self._db.execute(
            base_query
            .order_by(Clip.pinned.desc(), Clip.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        clips = list(data_result.scalars().all())

        return ClipListResponse(
            clips=[ClipResponse.model_validate(c) for c in clips],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_clip(
        self, clip_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[ClipResponse]:
        """Fetches a single clip by ID, scoped to the given user.

        Args:
            clip_id:  The clip's primary key.
            user_id:  Must match clip.user_id (ownership check).

        Returns:
            ClipResponse if found and owned by user, else None.
        """
        result = await self._db.execute(
            select(Clip).where(Clip.id == clip_id, Clip.user_id == user_id)
        )
        clip = result.scalar_one_or_none()
        return ClipResponse.model_validate(clip) if clip else None

    async def update_clip(
        self, clip_id: uuid.UUID, user_id: uuid.UUID, payload: ClipUpdate
    ) -> Optional[ClipResponse]:
        """Partially updates a clip's mutable fields.

        Args:
            clip_id:  The clip to update.
            user_id:  Ownership check.
            payload:  ClipUpdate with only the fields to change.

        Returns:
            Updated ClipResponse, or None if not found / not owned.
        """
        result = await self._db.execute(
            select(Clip).where(Clip.id == clip_id, Clip.user_id == user_id)
        )
        clip = result.scalar_one_or_none()
        if not clip:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(clip, field, value)

        # Re-classify if text changed
        if "text" in update_data:
            clip.category = classify(clip.text)
            # Phase 4: re-enqueue embedding generation
            # generate_embedding.delay(str(clip.id))

        await self._db.flush()
        await self._db.refresh(clip)
        return ClipResponse.model_validate(clip)

    async def delete_clip(self, clip_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Deletes a clip if it exists and is owned by the user.

        Args:
            clip_id:  Clip to delete.
            user_id:  Ownership check.

        Returns:
            True if deleted, False if not found.
        """
        result = await self._db.execute(
            select(Clip).where(Clip.id == clip_id, Clip.user_id == user_id)
        )
        clip = result.scalar_one_or_none()
        if not clip:
            return False
        await self._db.delete(clip)
        return True

    async def toggle_pin(
        self, clip_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[ClipResponse]:
        """Toggles the pinned state of a clip.

        Args:
            clip_id:  Clip to pin or unpin.
            user_id:  Ownership check.

        Returns:
            Updated ClipResponse, or None if not found.
        """
        result = await self._db.execute(
            select(Clip).where(Clip.id == clip_id, Clip.user_id == user_id)
        )
        clip = result.scalar_one_or_none()
        if not clip:
            return None
        clip.pinned = not clip.pinned
        await self._db.flush()
        await self._db.refresh(clip)
        return ClipResponse.model_validate(clip)

    async def search_clips(
        self, user_id: uuid.UUID, query: ClipSearchQuery
    ) -> ClipListResponse:
        """Searches clips using full-text or semantic search.

        For full-text (default), runs a case-insensitive ILIKE search across
        text, source_title, and source_url.

        For semantic search (`query.semantic=True`), delegates to
        search_service.semantic_search which uses pgvector cosine similarity
        blended with recency scoring (Phase 4).

        Args:
            user_id:  Scopes the search to this user's clips.
            query:    ClipSearchQuery with the search term and options.

        Returns:
            ClipListResponse with ranked results.
        """
        if query.semantic:
            results = await semantic_search(
                db=self._db,
                user_id=user_id,
                query_text=query.query,
                space_id=query.space_id,
                limit=query.limit,
                offset=query.offset,
            )
            return results

        # Full-text search via ILIKE
        q = f"%{query.query}%"
        base_query = (
            select(Clip)
            .where(
                Clip.user_id == user_id,
                or_(
                    Clip.text.ilike(q),
                    Clip.source_title.ilike(q),
                    Clip.source_url.ilike(q),
                ),
            )
        )
        if query.space_id:
            base_query = base_query.where(Clip.space_id == query.space_id)
        if query.category:
            base_query = base_query.where(Clip.category == query.category)

        count_result = await self._db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        data_result = await self._db.execute(
            base_query
            .order_by(Clip.pinned.desc(), Clip.created_at.desc())
            .offset(query.offset)
            .limit(query.limit)
        )
        clips = list(data_result.scalars().all())

        return ClipListResponse(
            clips=[ClipResponse.model_validate(c) for c in clips],
            total=total,
            offset=query.offset,
            limit=query.limit,
        )

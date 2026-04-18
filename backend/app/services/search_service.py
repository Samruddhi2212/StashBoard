"""Semantic search service using pgvector cosine similarity.

Phase 4 feature — this module is scaffolded but not active until
the pgvector extension is installed and embeddings are generated.

Scoring formula:
    final_score = 0.7 * cosine_similarity + 0.3 * recency_score

Recency score:
    A normalized value in [0, 1] inversely proportional to clip age.
    Clips from the last 24 hours score ~1.0; clips from 30 days ago score ~0.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Clip
from app.schemas import ClipListResponse, ClipResponse


def _recency_score(created_at: datetime, max_age_days: int = 30) -> float:
    """Computes a [0, 1] recency score for a clip.

    Args:
        created_at:    When the clip was created.
        max_age_days:  Age beyond which clips score 0.

    Returns:
        Float in [0.0, 1.0] — higher means more recent.
    """
    now = datetime.now(timezone.utc)
    age_seconds = (now - created_at.replace(tzinfo=timezone.utc)).total_seconds()
    max_seconds = max_age_days * 86400
    return max(0.0, 1.0 - age_seconds / max_seconds)


async def semantic_search(
    db: AsyncSession,
    user_id: uuid.UUID,
    query_text: str,
    space_id: Optional[uuid.UUID] = None,
    limit: int = 20,
    offset: int = 0,
) -> ClipListResponse:
    """Finds clips semantically similar to query_text.

    Encodes query_text with the same sentence-transformers model used during
    ingestion (all-MiniLM-L6-v2, 384 dimensions), then uses pgvector's
    cosine distance operator (<->) to rank results. A recency bonus
    (weight=0.3) is blended in to surface recent matches over stale ones.

    Args:
        db:          Async database session.
        user_id:     Scopes search to this user's clips.
        query_text:  The natural language query from the user.
        space_id:    Optional space to restrict search within.
        limit:       Maximum number of results.
        offset:      Pagination offset.

    Returns:
        ClipListResponse sorted by blended similarity + recency score.

    Note:
        Returns an empty result set if sentence-transformers or pgvector
        is not installed, rather than raising an error. This allows the
        codebase to run locally without ML dependencies.
    """
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError:
        return ClipListResponse(clips=[], total=0, offset=offset, limit=limit)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_embedding = model.encode(query_text, normalize_embeddings=True).tolist()

    # Fetch candidates via cosine distance (pgvector)
    candidate_limit = min(limit * 5, 200)  # Fetch more to blend recency in Python
    space_filter = "AND space_id = :space_id" if space_id else ""

    raw_sql = text(f"""
        SELECT id,
               1 - (embedding <-> CAST(:embedding AS vector)) AS cosine_sim
        FROM   clips
        WHERE  user_id = :user_id
          AND  embedding IS NOT NULL
          {space_filter}
        ORDER  BY embedding <-> CAST(:embedding AS vector)
        LIMIT  :limit
    """)

    params: dict = {
        "embedding": str(query_embedding),
        "user_id":   str(user_id),
        "limit":     candidate_limit,
    }
    if space_id:
        params["space_id"] = str(space_id)

    result = await db.execute(raw_sql, params)
    rows = result.fetchall()

    if not rows:
        return ClipListResponse(clips=[], total=0, offset=offset, limit=limit)

    # Fetch full clip objects
    clip_ids = [row[0] for row in rows]
    sim_map  = {row[0]: float(row[1]) for row in rows}

    clips_result = await db.execute(select(Clip).where(Clip.id.in_(clip_ids)))
    clips = list(clips_result.scalars().all())

    # Blend similarity with recency
    scored: list[tuple[float, Clip]] = []
    for clip in clips:
        cosine = sim_map.get(clip.id, 0.0)
        recency = _recency_score(clip.created_at)
        blended = 0.7 * cosine + 0.3 * recency
        scored.append((blended, clip))

    scored.sort(key=lambda x: x[0], reverse=True)
    total = len(scored)
    page = [c for _, c in scored[offset: offset + limit]]

    return ClipListResponse(
        clips=[ClipResponse.model_validate(c) for c in page],
        total=total,
        offset=offset,
        limit=limit,
    )

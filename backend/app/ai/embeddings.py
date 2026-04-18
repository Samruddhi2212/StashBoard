"""Celery task for generating sentence-transformer embeddings for clips.

Phase 4 feature — activated when the Celery worker is running alongside
the FastAPI server.

Model: sentence-transformers/all-MiniLM-L6-v2
  - 384-dimensional output
  - ~80MB download on first use
  - ~14k tokens/sec on CPU; 2-3ms/clip on GPU

The task combines clip.text with clip.source_title for a richer semantic
representation, since the title often provides context not in the copied text
(e.g., copying a phone number from a contact page — the title "John Doe |
LinkedIn" encodes meaning that the number alone does not).
"""

from __future__ import annotations

import uuid

from celery import Celery  # type: ignore

from app.config import settings

celery_app = Celery(
    "stashboard",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_embedding(self, clip_id: str) -> dict:
    """Generates and stores a 384-dim embedding for the given clip.

    Imports are deferred inside the task function so the Celery worker
    process can start without requiring heavy ML libraries in the web process.

    Args:
        clip_id: String UUID of the Clip record to embed.

    Returns:
        A dict with keys: clip_id, dimensions, success.

    Raises:
        Retries up to 3 times on transient failures (network, DB lock, etc.).
    """
    try:
        import asyncio

        from sentence_transformers import SentenceTransformer  # type: ignore
        from sqlalchemy import select

        from app.database import AsyncSessionLocal
        from app.models import Clip

        model = SentenceTransformer("all-MiniLM-L6-v2")

        async def _run() -> bool:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Clip).where(Clip.id == uuid.UUID(clip_id))
                )
                clip = result.scalar_one_or_none()
                if not clip:
                    return False

                # Combine text with source title for richer context
                combined = clip.text
                if clip.source_title:
                    combined = f"{clip.source_title}\n\n{clip.text}"

                embedding = model.encode(
                    combined,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ).tolist()

                clip.embedding = embedding
                await db.commit()
                return True

        loop = asyncio.new_event_loop()
        try:
            success = loop.run_until_complete(_run())
        finally:
            loop.close()

        return {"clip_id": clip_id, "dimensions": 384, "success": success}

    except Exception as exc:
        raise self.retry(exc=exc)

"""FastAPI application entry point for the Stashboard backend.

Phase 3 — this file wires up all routers, CORS, lifespan, and health check.
The extension communicates directly with chrome.storage.local in Phase 1;
this backend activates in Phase 3 for cross-device sync and AI features.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routes import auth, clips, spaces, sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup; dispose engine on shutdown."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend API for Stashboard — smart clipboard manager with semantic search.\n\n"
        "Phase 1: Chrome extension with local storage only.\n"
        "Phase 3: This backend activates for sync, AI, and team features."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router,   prefix="/api/auth",   tags=["auth"])
app.include_router(clips.router,  prefix="/api/clips",  tags=["clips"])
app.include_router(spaces.router, prefix="/api/spaces", tags=["spaces"])
app.include_router(sync.router,   prefix="/api/sync",   tags=["sync"])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["infra"])
async def health_check() -> dict:
    """Simple health check endpoint for load balancers and uptime monitoring."""
    return {"status": "ok", "version": settings.app_version}

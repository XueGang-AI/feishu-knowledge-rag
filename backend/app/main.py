from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.routes.health import router as health_router
from backend.app.routes.rag import router as rag_router
from backend.app.routes.reindex import router as reindex_router
from backend.app.routes.sources import router as sources_router
from backend.app.routes.sync import router as sync_router
from backend.app.services.weekly_scheduler import WeeklyScanScheduler


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scheduler = WeeklyScanScheduler(settings)
        app.state.weekly_scan_scheduler = scheduler
        scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()

    app = FastAPI(
        title="Feishu Knowledge RAG",
        version="0.1.0",
        description="Local-first RAG backend for Feishu knowledge bases.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(rag_router, prefix="/api")
    app.include_router(reindex_router, prefix="/api")
    app.include_router(sources_router, prefix="/api")
    app.include_router(sync_router, prefix="/api")

    return app


app = create_app()

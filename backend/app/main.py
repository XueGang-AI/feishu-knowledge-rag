from fastapi import FastAPI

from backend.app.routes.health import router as health_router
from backend.app.routes.sync import router as sync_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Feishu Knowledge RAG",
        version="0.1.0",
        description="Local-first RAG backend for Feishu knowledge bases.",
    )
    app.include_router(health_router)
    app.include_router(sync_router, prefix="/api")
    return app


app = create_app()

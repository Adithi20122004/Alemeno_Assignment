from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import jobs as jobs_routes
from app.core.config import settings
from app.core.logging import configure_logging
from app.database.session import Base, engine

configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="Async CSV → cleaned transactions + anomaly detection + Gemini LLM insights.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(jobs_routes.router, prefix="/jobs", tags=["jobs"])

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {"app": settings.APP_NAME, "status": "ok", "docs": "/docs"}

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "healthy"}

    @app.on_event("startup")
    def _startup() -> None:
        # Alembic is the source of truth; this is a safety net for local dev.
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as exc:  # pragma: no cover
            logger.warning("create_all skipped: %s", exc)
        logger.info("%s started (env=%s)", settings.APP_NAME, settings.APP_ENV)

    return app


app = create_app()

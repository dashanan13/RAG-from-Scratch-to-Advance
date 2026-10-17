"""Stage 11 - FastAPI application entry point.

Wires the online pipeline (query -> retrieve -> rerank -> context -> generate)
behind an HTTP API. Run with:
    uvicorn production.api.main:create_app --factory --host 0.0.0.0 --port 8000
"""
from __future__ import annotations


def create_app():
    """Build and return the FastAPI app, warming the pipeline engine on startup."""
    from fastapi import FastAPI

    from ..pipeline import build_offline_index
    from .routes import router

    app = FastAPI(title="Shakespeare Evidence Desk", version="1.0")
    app.include_router(router)

    @app.on_event("startup")
    def _warm() -> None:
        # Load artifacts and build the in-memory engine once, so the first request is not slow.
        build_offline_index()

    return app

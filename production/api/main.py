"""Stage 11 - FastAPI application entry point.

Wires the online pipeline (query -> retrieve -> rerank -> context -> generate)
behind an HTTP API. Run with:
    uvicorn production.api.main:create_app --factory --host 0.0.0.0 --port 8000
"""
from __future__ import annotations


def create_app():
    """Build and return the FastAPI app, warming the pipeline engine on startup."""
    import logging
    from pathlib import Path

    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    from ..pipeline import build_offline_index
    from .routes import router

    app = FastAPI(title="Shakespeare Evidence Desk", version="1.0")
    app.include_router(router)

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def _portal() -> FileResponse:
        # Serve the chat web portal so the service can be tested from a browser.
        return FileResponse(static_dir / "index.html")

    @app.on_event("startup")
    def _warm() -> None:
        # Warm the in-memory engine once so the first request is fast. Degrade instead of crashing
        # when the prebuilt index artifact or Azure identity is unavailable, so the portal still loads.
        try:
            build_offline_index()
        except Exception as exc:  # noqa: BLE001 - surface the cause, keep the service up
            logging.getLogger("uvicorn.error").warning(
                "Engine warm-up skipped: %s. Build .artifacts (notebooks 01-04) and mount an Azure identity.",
                exc,
            )

    return app

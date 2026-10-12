"""Stage 11 - FastAPI application entry point.

Wires the online pipeline (query -> retrieve -> rerank -> context -> generate)
behind an HTTP API. Implemented in `experiments/11`; dependencies (fastapi,
uvicorn) are added then.
"""
from __future__ import annotations

# from fastapi import FastAPI
# from .routes import router
#
# app = FastAPI(title="Shakespeare Evidence Desk")
# app.include_router(router)


def create_app():
    """Build and return the FastAPI app."""
    raise NotImplementedError("Fill from experiments/11.")

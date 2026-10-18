"""Stage 11 - API routes: query and evidence endpoints.

Defines ``/ask`` (grounded answer) and ``/retrieve_evidence`` (reusable tool),
each returning citations, scores, and a request id, plus ``/healthz``.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

MAX_QUERY_CHARS = 2000   # input guardrail: reject oversized prompts before any model call


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_CHARS)


class EvidenceRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_CHARS)
    top_k: int = Field(5, ge=1, le=20)


@router.get("/healthz")
def healthz() -> dict:
    """Liveness probe; readiness is confirmed by the startup engine warm-up."""
    return {"status": "ok"}


@router.post("/ask")
def ask(request: AskRequest) -> dict:
    from ..pipeline import safe_answer_traced

    # safe_answer_traced screens the input, degrades gracefully, and returns a per-stage trace for the UI.
    return safe_answer_traced(request.query)


@router.post("/retrieve_evidence")
def retrieve_evidence_route(request: EvidenceRequest) -> dict:
    from ..pipeline import retrieve_evidence

    try:
        return retrieve_evidence(request.query, top_k=request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

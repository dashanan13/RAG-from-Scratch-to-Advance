"""`retrieve_evidence` tool for LLM function calling.

Returns passages, source locations, versions, scores, and a request id so
another LLM app can ground on the same authorized evidence.
"""
from __future__ import annotations


def retrieve_evidence(query: str, top_k: int = 5) -> dict:
    """Return ``{'passages': [...], 'request_id': str}`` for tool use."""
    raise NotImplementedError("Fill once retrieval (05-07) is selected.")

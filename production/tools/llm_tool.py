"""`retrieve_evidence` tool for LLM function calling.

Returns passages, source locations, and a request id so another LLM app can
ground on the same authorized evidence. Thin wrapper over the online pipeline.
"""
from __future__ import annotations

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "retrieve_evidence",
        "description": "Retrieve cited passages from the Shakespeare corpus for a query, without generating an answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question to find evidence for."},
                "top_k": {"type": "integer", "description": "How many passages to return.", "default": 5},
            },
            "required": ["query"],
        },
    },
}


def retrieve_evidence(query: str, top_k: int = 5) -> dict:
    """Return ``{'passages': [...], 'request_id': str}`` for tool use."""
    from ..pipeline import retrieve_evidence as _retrieve

    return _retrieve(query, top_k=top_k)

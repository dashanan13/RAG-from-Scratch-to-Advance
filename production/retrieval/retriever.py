"""Stage 05 - Retrieval: search the index for candidate passages.

Dense / keyword / hybrid choice, top-k, and filters are selected in
`experiments/05`.
"""
from __future__ import annotations


def retrieve(query: str, top_k: int = 5, filters: dict | None = None) -> list[dict]:
    """Return ranked candidate passages with scores and provenance."""
    raise NotImplementedError("Fill from experiments/05.")

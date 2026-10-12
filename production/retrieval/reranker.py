"""Stage 06 - Reranking: reorder candidates by relevance.

Compares none / semantic / bounded-LLM reranking in `experiments/06`.
"""
from __future__ import annotations


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    """Return candidates reordered by relevance."""
    raise NotImplementedError("Fill from experiments/06.")

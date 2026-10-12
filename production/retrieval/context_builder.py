"""Stage 07 - Context building: assemble passages and citations.

Deduplication, parent context, and token-budget policy are selected in
`experiments/07`.
"""
from __future__ import annotations


def build_context(query: str, passages: list[dict], token_budget: int = 2000) -> dict:
    """Return ``{'context': str, 'citations': list[dict]}`` within budget."""
    raise NotImplementedError("Fill from experiments/07.")

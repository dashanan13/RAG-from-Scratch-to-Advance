"""Stage 05 - Hybrid search: fuse keyword and vector results.

Reciprocal rank fusion and weighting are selected in `experiments/05`.
"""
from __future__ import annotations


def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """Return fused keyword + vector results."""
    raise NotImplementedError("Fill from experiments/05.")

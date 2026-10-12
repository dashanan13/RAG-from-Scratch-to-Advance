"""Stage 10 - Metrics: retrieval and answer-quality scores.

Definitions (Recall@k, MRR, citation support, abstention correctness) are
finalized in `experiments/10`.
"""
from __future__ import annotations


def recall_at_k(expected: set[str], retrieved: list[str], k: int) -> float:
    raise NotImplementedError("Fill from experiments/10.")


def reciprocal_rank(expected: set[str], retrieved: list[str]) -> float:
    raise NotImplementedError("Fill from experiments/10.")

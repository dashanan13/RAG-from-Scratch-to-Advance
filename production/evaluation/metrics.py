"""Stage 10 - Metrics: retrieval and answer-quality scores.

Definitions (Recall@k, MRR, citation support, abstention correctness) are
finalized in `experiments/10`. Retrieval metrics are judge-free and work at the
level of source works (the gold label is the set of expected works).
"""
from __future__ import annotations

import re

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def recall_at_k(expected: set[str], retrieved: list[str], k: int) -> float:
    """Fraction of expected works that appear in the first ``k`` retrieved works."""
    if not expected:
        return 1.0
    top = set(retrieved[:k])
    return sum(1 for work in expected if work in top) / len(expected)


def reciprocal_rank(expected: set[str], retrieved: list[str]) -> float:
    """One over the rank of the first retrieved work that is expected, else 0."""
    if not expected:
        return 1.0
    for rank, work in enumerate(retrieved, start=1):
        if work in expected:
            return 1.0 / rank
    return 0.0


def citation_support(answer: str, citations: list[dict]) -> bool:
    """True when the answer cites at least one passage and every marker resolves to a provided citation."""
    markers = {int(m) for m in _CITATION_PATTERN.findall(answer)}
    valid = {c.get("marker") for c in citations}
    return bool(markers) and markers.issubset(valid)


def abstention_correct(answer: str, answerable: bool, sentinel: str = "INSUFFICIENT_CONTEXT") -> bool:
    """True when the system abstains exactly on unanswerable questions and answers the answerable ones."""
    abstained = sentinel in answer.upper()
    return (not abstained) if answerable else abstained

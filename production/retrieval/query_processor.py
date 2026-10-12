"""Stage 09 - Query processing: normalize, rewrite, and embed the query.

Rewriting / decomposition strategy is selected in `experiments/09`.
"""
from __future__ import annotations


def process_query(query: str) -> dict:
    """Return ``{'normalized': str, 'variants': list[str], 'embedding': list[float]}``."""
    raise NotImplementedError("Fill from experiments/09.")

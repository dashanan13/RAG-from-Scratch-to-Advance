"""Stage 08 - Grounded generation: answer only from retrieved context.

Grounding prompt, citation format, and abstention rules are selected in
`experiments/08`.
"""
from __future__ import annotations


def generate_answer(query: str, context: dict) -> dict:
    """Return ``{'answer': str, 'citations': list[dict], 'abstained': bool}``."""
    raise NotImplementedError("Fill from experiments/08.")

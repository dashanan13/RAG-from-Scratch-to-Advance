"""Stage 01 - Parsing: structure a play into source-linked blocks.

Selected approach (experiments/01): deterministic rules with a model-assisted
fallback for plays whose line coverage falls below the threshold.
"""
from __future__ import annotations


def parse_play(work_id: str, title: str, body: str) -> dict:
    """Return ``{'front_matter': str, 'blocks': list[dict]}``."""
    raise NotImplementedError("Fill from experiments/01 Section 4.")

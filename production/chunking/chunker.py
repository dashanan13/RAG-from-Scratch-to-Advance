"""Stage 02 - Chunking: split parsed blocks into retrieval units.

Selected strategy is chosen in `experiments/02` (fixed / overlapping /
scene- or speech-aware). Chunks keep provenance back to source blocks.
"""
from __future__ import annotations


def chunk_blocks(blocks: list[dict]) -> list[dict]:
    """Return a list of chunk dicts with text and source provenance."""
    raise NotImplementedError("Fill from experiments/02.")

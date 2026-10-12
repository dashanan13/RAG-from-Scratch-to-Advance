"""Stage 01 - Ingestion pipeline: corpus to parsed blocks.

Orchestrates loaders -> preprocess -> parser and returns the blocks consumed by
the chunking stage.
"""
from __future__ import annotations


def run_ingestion() -> list[dict]:
    """Load, preprocess, and parse all plays into source-linked blocks."""
    raise NotImplementedError("Compose loaders, preprocess, and parser here.")

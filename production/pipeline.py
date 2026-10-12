"""Top-level orchestration of the end-to-end RAG pipeline.

Composes the selected per-stage implementations into offline (build index) and
online (answer a query) flows. Each function delegates to the stage modules so
the final service reflects the experiment selections, not notebook state.
"""
from __future__ import annotations


def build_offline_index() -> None:
    """Ingest -> chunk -> embed -> index the corpus."""
    raise NotImplementedError("Compose stages 01-04 once each is selected.")


def answer(query: str) -> dict:
    """Online flow: query -> retrieve -> rerank -> context -> generate."""
    raise NotImplementedError("Compose stages 05-09 once each is selected.")

"""Stage 01 - Ingestion: fetch and read the verified corpus.

Final selection from `experiments/01`. Downloads the exact blobs named in the
setup handoff (identity auth) and returns their raw text, cached locally.
"""
from __future__ import annotations

from pathlib import Path


def load_corpus(handoff: dict, cache_dir: Path) -> dict[str, str]:
    """Return ``{document_id: raw_text}`` for every document in the handoff."""
    raise NotImplementedError("Fill from experiments/01 Section 2.")

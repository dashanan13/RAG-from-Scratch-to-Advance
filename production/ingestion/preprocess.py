"""Stage 01 - Preprocessing: isolate Project Gutenberg administrative notices.

Separates the license header/footer from the play body while preserving the
original text, as selected in `experiments/01`.
"""
from __future__ import annotations


def split_gutenberg(text: str) -> dict:
    """Return ``{'header_notice', 'body', 'footer_notice'}``."""
    raise NotImplementedError("Fill from experiments/01 Section 3.")

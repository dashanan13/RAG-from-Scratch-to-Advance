"""Stage 03 - Embeddings: encode text with the hosted embedding deployment.

Model, dimensions, normalization, and batching are selected in
`experiments/03`.
"""
from __future__ import annotations


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text."""
    raise NotImplementedError("Fill from experiments/03.")

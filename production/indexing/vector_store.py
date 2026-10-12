"""Stage 04 - Vector store abstraction over Azure AI Search.

Index type, ANN parameters, and metadata schema are selected in
`experiments/04`.
"""
from __future__ import annotations


class VectorStore:
    def upsert(self, records: list[dict]) -> None:
        raise NotImplementedError("Fill from experiments/04.")

    def search(self, vector: list[float], top_k: int = 5, filters: dict | None = None) -> list[dict]:
        raise NotImplementedError("Fill from experiments/04.")

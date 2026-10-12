"""Shared configuration for the production RAG service.

Loads settings from the repository `.env` (the same file the experiment
notebooks use) so production code and experiments never drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values


def _find_root(start: Path | None = None) -> Path:
    path = (start or Path(__file__)).resolve()
    for candidate in [path, *path.parents]:
        if (candidate / ".env.example").is_file():
            return candidate
    raise RuntimeError("Could not locate repository root (.env.example not found).")


@dataclass(frozen=True)
class Settings:
    azure_openai_endpoint: str
    azure_openai_api_version: str
    chat_deployment: str
    embedding_deployment: str
    phoenix_collector_endpoint: str | None
    root: Path
    artifacts: Path


@lru_cache
def get_settings() -> Settings:
    root = _find_root()
    values = {key: value for key, value in dotenv_values(root / ".env").items() if value}
    return Settings(
        azure_openai_endpoint=values.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_api_version=values.get("AZURE_OPENAI_API_VERSION", ""),
        chat_deployment=values.get("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
        embedding_deployment=values.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", ""),
        phoenix_collector_endpoint=values.get("PHOENIX_COLLECTOR_ENDPOINT") or None,
        root=root,
        artifacts=root / ".artifacts",
    )

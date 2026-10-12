"""Shared hosted-model client, built keyless with Microsoft Entra identity.

Mirrors the connection pattern established in `experiments/00` so production
and notebooks authenticate identically (no API keys stored).
"""
from __future__ import annotations

from functools import lru_cache

from .settings import get_settings


@lru_cache
def get_openai_client():
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    settings = get_settings()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
        azure_ad_token_provider=token_provider,
    )

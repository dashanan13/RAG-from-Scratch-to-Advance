"""Stage 09 - Query processing: normalize, decompose, and embed the query.

The query-handling policy (decomposition with multi-query fusion) is selected
in `experiments/09`: multi-target questions are split into independent
sub-queries so retrieval can cover every work the question touches, while the
grounding contract in stage 08 keeps authority over abstention.
"""
from __future__ import annotations

import json
import re

MAX_SUBQUERIES = 3

DECOMPOSE_SYSTEM = (
    "You split questions for a Shakespeare evidence desk whose corpus is a fixed set of plays. "
    "If the question targets several plays, characters, or parts at once (a comparison, an ambiguous "
    "name that appears in multiple plays, or a multi-part ask), break it into independent sub-questions, "
    "each aimed at ONE play or entity. If it already targets a single thing, return it unchanged as the "
    f"only sub-question. Return at most {MAX_SUBQUERIES} sub-questions, preserve intent, and do not answer. "
    'Return a JSON object {"subqueries": ["...", "..."]}.'
)


def _decompose(query: str) -> list[str]:
    """Split a multi-target question into up to three independent sub-queries."""
    from ..clients import get_openai_client
    from ..settings import get_settings

    settings = get_settings()
    client = get_openai_client()
    response = client.chat.completions.create(
        model=settings.chat_deployment,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": DECOMPOSE_SYSTEM},
            {"role": "user", "content": query},
        ],
    )
    match = re.search(r"\{.*\}", response.choices[0].message.content or "{}", re.DOTALL)
    parsed = json.loads(match.group(0)) if match else {}
    subs = [str(sub).strip() for sub in parsed.get("subqueries", []) if str(sub).strip()]
    return subs[:MAX_SUBQUERIES] or [query]


def process_query(query: str) -> dict:
    """Return ``{'normalized': str, 'variants': list[str], 'embedding': list[float]}``.

    ``normalized`` is the original question (the decompose policy does not rewrite it),
    ``variants`` are the sub-queries retrieval fans out and fuses, and ``embedding`` is
    the normalized query's vector for the dense leg of retrieval.
    """
    from ..clients import get_openai_client
    from ..settings import get_settings

    settings = get_settings()
    client = get_openai_client()

    normalized = query.strip()
    variants = _decompose(normalized)
    embedding = client.embeddings.create(
        model=settings.embedding_deployment, input=[normalized]
    ).data[0].embedding
    return {"normalized": normalized, "variants": variants, "embedding": embedding}

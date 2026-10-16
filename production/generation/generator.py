"""Stage 08 - Grounded generation: answer only from retrieved context.

Grounding prompt, citation format, and abstention rules are selected in
`experiments/08` (the strict grounding contract).
"""
from __future__ import annotations

import re

ABSTAIN_SENTINEL = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = (
    "You are a Shakespeare evidence desk that answers strictly from provided passages.\n"
    "Rules:\n"
    "1. Use ONLY the numbered passages in the context. Do not use any outside knowledge.\n"
    "2. Cite every claim with the bracketed passage number(s) it comes from, e.g. [1] or [2][3].\n"
    "3. State facts the passages support first; clearly mark any interpretation as such.\n"
    f"4. If the passages do not contain enough information to answer, reply with exactly {ABSTAIN_SENTINEL} and nothing else.\n"
    "Be concise and do not invent passages, citations, speakers, or scenes."
)

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def generate_answer(query: str, context: dict, *, max_completion_tokens: int = 2000) -> dict:
    """Return ``{'answer': str, 'citations': list[dict], 'abstained': bool}``."""
    from ..clients import get_openai_client
    from ..settings import get_settings

    settings = get_settings()
    client = get_openai_client()
    context_text = context.get("context", "")
    passage_citations = context.get("citations", [])

    # gpt-5 reasoning models only accept the default temperature; the budget covers reasoning tokens plus the answer.
    response = client.chat.completions.create(
        model=settings.chat_deployment,
        max_completion_tokens=max_completion_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {query}"},
        ],
    )
    answer = (response.choices[0].message.content or "").strip()
    abstained = ABSTAIN_SENTINEL in answer.upper()

    # Keep only the citations the answer actually referenced, so callers can resolve markers to source lines.
    cited = {int(marker) for marker in _CITATION_PATTERN.findall(answer)}
    used_citations = [c for c in passage_citations if c.get("marker") in cited]
    return {"answer": answer, "citations": used_citations, "abstained": abstained}

"""Top-level orchestration of the end-to-end RAG pipeline.

Composes the selected per-stage implementations into offline (build index) and
online (answer a query) flows. The online flow reads the stage handoffs so the
service reflects the experiment selections, not notebook state, and shares the
`.artifacts` on-disk caches with the notebooks so repeated calls are cheap.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

_WORD_PATTERN = re.compile(r"[a-z0-9']+")
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def _tokenize(text: str) -> list[str]:
    return _WORD_PATTERN.findall(text.lower())


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _l2_normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(v * v for v in vector))
    return [v / length for v in vector] if length else vector


def _with_retry(call: Callable[[], Any], attempts: int = 3, base_delay: float = 0.5) -> Any:
    """Retry a transient provider call with exponential backoff; re-raise after the last attempt."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception:  # provider/transient errors; stage 12 drills these paths
            if attempt == attempts - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))


class _BM25:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [_tokenize(text) for text in documents]
        self.lengths = [len(tokens) for tokens in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.docs)) if self.docs else 0.0
        self.counts: list[dict[str, int]] = []
        document_frequency: dict[str, int] = defaultdict(int)
        for tokens in self.docs:
            counts: dict[str, int] = defaultdict(int)
            for term in tokens:
                counts[term] += 1
            self.counts.append(counts)
            for term in counts:
                document_frequency[term] += 1
        total = len(self.docs)
        self.idf = {term: math.log(1 + (total - df + 0.5) / (df + 0.5)) for term, df in document_frequency.items()}

    def search(self, query: str, top_k: int) -> list[int]:
        terms = [t for t in _tokenize(query) if t in self.idf]
        scored: list[tuple[int, float]] = []
        for row, counts in enumerate(self.counts):
            length = self.lengths[row]
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                norm = self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
                score += self.idf[term] * (tf * (self.k1 + 1)) / (tf + norm)
            if score > 0:
                scored.append((row, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [row for row, _ in scored[:top_k]]


@dataclass
class _Engine:
    """In-memory, lazily built composition of the selected per-stage configuration."""

    records: list[dict]
    vectors: list[list[float]]
    bm25: _BM25
    chunks_by_id: dict[str, dict]
    siblings_by_work: dict[str, dict[int, str]]
    config: dict[str, str]
    params: dict[str, Any]
    client: Any = None
    caches: dict[str, Path] = field(default_factory=dict)

    def get_client(self):
        if self.client is None:
            from .clients import get_openai_client

            self.client = get_openai_client()
        return self.client


def _artifacts() -> Path:
    from .settings import get_settings

    return get_settings().artifacts


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def get_engine() -> _Engine:
    """Build (once) the online engine from the stage handoffs and the index artifact."""
    from .settings import get_settings

    settings = get_settings()
    artifacts = settings.artifacts
    index_path = artifacts / "index.json"
    if not index_path.is_file():
        raise RuntimeError("Missing .artifacts/index.json. Run the offline build (notebooks 01-04) first.")
    index_payload = _load_json(index_path)
    if index_payload.get("embedding_backend") != "hosted":
        raise RuntimeError("Index was not built on the hosted Azure backend; rebuild before serving.")

    def _optional(name: str, default: dict) -> dict:
        path = artifacts / name
        return _load_json(path) if path.is_file() else default

    retrieval = _optional("retrieval-handoff.json", {"selected_method": "dense"})
    reranking = _optional("reranking-handoff.json", {"selected_reranker": "none", "top_k": 5})
    context = _optional("context-handoff.json", {"selected_builder": "dedup-parent", "token_budget": 2000})
    generation = _optional("generation-handoff.json", {})
    query = _optional("query-handoff.json", {"selected_policy": "passthrough"})
    chunks_payload = _optional("chunks.json", {"chunks": []})

    records = index_payload["records"]
    chunks_by_id = {c["chunk_id"]: c for c in chunks_payload.get("chunks", [])}
    siblings_by_work: dict[str, dict[int, str]] = defaultdict(dict)
    for chunk_id, chunk in chunks_by_id.items():
        tail = chunk_id.rsplit(":", 1)[-1]
        if tail.isdigit():
            siblings_by_work[chunk.get("work_id")][int(tail)] = chunk_id

    bm25_params = retrieval.get("bm25_params", {"k1": 1.5, "b": 0.75})
    params: dict[str, Any] = {
        "index_type": index_payload["index_type"],
        "dims": index_payload["dims"],
        "ivf": index_payload.get("ivf"),
        "nprobe": index_payload.get("params", {}).get("nprobe", 8),
        "method": retrieval.get("selected_method", "dense"),
        "rrf_k": retrieval.get("rrf_k") or 60,
        "reranker": reranking.get("selected_reranker", "none"),
        "top_k": reranking.get("top_k", 5),
        "builder": context.get("selected_builder", "dedup-parent"),
        "token_budget": context.get("token_budget", 2000),
        "candidate_pool": context.get("candidate_pool", reranking.get("rerank_pool", 20)),
        "dedup_threshold": context.get("dedup", {}).get("threshold", 0.6),
        "parent_neighbors": context.get("parent_context", {}).get("neighbors_each_side", 1),
        "parent_max_tokens": context.get("parent_context", {}).get("max_tokens", 700),
        "contract": generation.get("selected_contract", "strict"),
        "system_prompt": generation.get("system_prompt", ""),
        "uses_context": generation.get("uses_context", True),
        "max_completion_tokens": generation.get("max_completion_tokens", 2000),
        "sentinel": generation.get("abstention", {}).get("sentinel", "INSUFFICIENT_CONTEXT"),
        "policy": query.get("selected_policy", "passthrough"),
        "policy_params": query.get("policy_parameters", {}),
        "prompts": query.get("prompts", {}),
    }
    config = {k: v for k, v in dotenv_from(settings.root).items() if v}
    caches = {name: artifacts / name for name in ("embedding-cache", "generation-cache", "query-cache")}
    for path in caches.values():
        path.mkdir(parents=True, exist_ok=True)
    return _Engine(
        records=records,
        vectors=[r["embedding"] for r in records],
        bm25=_BM25([r["text"] for r in records], bm25_params.get("k1", 1.5), bm25_params.get("b", 0.75)),
        chunks_by_id=chunks_by_id,
        siblings_by_work=siblings_by_work,
        config=config,
        params=params,
        caches=caches,
    )


def dotenv_from(root: Path) -> dict[str, str]:
    from dotenv import dotenv_values

    return {k: v for k, v in dotenv_values(root / ".env").items() if v}


# --------------------------------------------------------------------------- #
# Online flow: query -> retrieve -> rerank -> context -> generate
# --------------------------------------------------------------------------- #
def _embed(engine: _Engine, text: str) -> list[float]:
    deployment = engine.config["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
    cache = engine.caches["embedding-cache"] / (hashlib.sha256(f"{deployment}|{text}".encode()).hexdigest() + ".json")
    if cache.is_file():
        vector = json.loads(cache.read_text())
    else:
        client = engine.get_client()
        vector = _with_retry(lambda: client.embeddings.create(model=deployment, input=[text]).data[0].embedding)
        cache.write_text(json.dumps(vector))
    return _l2_normalize(vector[: engine.params["dims"]])


def _dense(engine: _Engine, query_vector: list[float], k: int) -> list[int]:
    params = engine.params
    if params["index_type"] == "ivf" and params["ivf"]:
        centroids = params["ivf"]["centroids"]
        lists = {int(c): rows for c, rows in params["ivf"]["lists"].items()}
        nearest = sorted(range(len(centroids)), key=lambda c: _dot(query_vector, centroids[c]), reverse=True)[: params["nprobe"]]
        pool = [i for c in nearest for i in lists.get(c, ())]
        return sorted(pool, key=lambda i: _dot(query_vector, engine.vectors[i]), reverse=True)[:k]
    return sorted(range(len(engine.vectors)), key=lambda i: _dot(query_vector, engine.vectors[i]), reverse=True)[:k]


def _rrf(rankings: list[list[int]], damping: int, top_k: int) -> list[int]:
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, row in enumerate(ranking):
            scores[row] += 1.0 / (damping + rank + 1)
    return [row for row, _ in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]]


def _retrieve_pool(engine: _Engine, text: str, vector: list[float], pool_size: int) -> list[int]:
    method = engine.params["method"]
    if method == "bm25":
        return engine.bm25.search(text, pool_size)
    if method == "dense":
        return _dense(engine, vector, pool_size)
    return _rrf([_dense(engine, vector, pool_size), engine.bm25.search(text, pool_size)], engine.params["rrf_k"], pool_size)


def _query_json(engine: _Engine, system_prompt: str, user_text: str, operation: str) -> dict:
    deployment = engine.config["AZURE_OPENAI_CHAT_DEPLOYMENT"]
    cache = engine.caches["query-cache"] / (hashlib.sha256(f"{deployment}|{operation}|{user_text}".encode()).hexdigest() + ".json")
    if cache.is_file():
        return json.loads(cache.read_text())
    client = engine.get_client()
    response = _with_retry(lambda: client.chat.completions.create(
        model=deployment, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]))
    match = re.search(r"\{.*\}", response.choices[0].message.content or "{}", re.DOTALL)
    parsed = json.loads(match.group(0)) if match else {}
    cache.write_text(json.dumps(parsed))
    return parsed


def _shape_query(engine: _Engine, query: str) -> tuple[str, list[str]]:
    """Apply the stage 09 selected query policy; return (primary, variants)."""
    policy = engine.params["policy"]
    prompts = engine.params["prompts"]
    max_subqueries = engine.params["policy_params"].get("max_subqueries", 3)
    if policy == "passthrough" or not prompts:
        return query, [query]
    if policy == "rewrite":
        rewritten = (_query_json(engine, prompts["rewrite_system"], query, "rewrite").get("query") or "").strip()
        return (rewritten or query), [rewritten or query]
    # decompose and adaptive both fan out; the online path uses a single bounded decomposition.
    subs = [str(s).strip() for s in _query_json(engine, prompts["decompose_system"], query, "decompose").get("subqueries", []) if str(s).strip()]
    subs = subs[:max_subqueries] or [query]
    return subs[0], subs


def _build_context(engine: _Engine, ordered_rows: list[int]) -> dict:
    encoder = _get_encoder()
    params = engine.params
    records = engine.records

    def passage_block(position: int, record: dict, text: str) -> str:
        scenes = record.get("scenes") or []
        scene = f"Act {scenes[0][0]}, Scene {scenes[0][1]}" if scenes else "Unknown scene"
        header = f"[{position}] {record['work']} - {scene}"
        if record.get("speakers"):
            header += f" ({', '.join(record['speakers'][:4])})"
        return f"{header}\n{text.strip()}"

    def parent_text(row: int) -> str:
        record = records[row]
        tail = record["chunk_id"].rsplit(":", 1)[-1]
        position = int(tail) if tail.isdigit() else None
        siblings = engine.siblings_by_work.get(record["work_id"], {})
        if position is None or not siblings:
            return record["text"]
        pieces = []
        for offset in range(-params["parent_neighbors"], params["parent_neighbors"] + 1):
            sibling = engine.chunks_by_id.get(siblings.get(position + offset, ""))
            if sibling and any(scene in record["scenes"] for scene in sibling.get("scenes", [])):
                pieces.append((position + offset, sibling["text"]))
        pieces.sort()
        seen, lines = set(), []
        for _, text in pieces:
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped and stripped in seen:
                    continue
                if stripped:
                    seen.add(stripped)
                lines.append(line)
        merged = "\n".join(lines).strip() or record["text"]
        ids = encoder.encode(merged)
        return encoder.decode(ids[: params["parent_max_tokens"]]) if len(ids) > params["parent_max_tokens"] else merged

    builder = params["builder"]
    budget = params["token_budget"]
    top_k = params["top_k"]
    kept, signatures, texts = [], [], []
    if builder == "raw":
        kept = list(ordered_rows[:top_k])
        texts = [records[row]["text"] for row in kept]
    else:
        used = 0
        for row in ordered_rows:
            signature = set(_tokenize(records[row]["text"]))
            if any((len(signature & prev) / len(signature | prev) if (signature | prev) else 0) >= params["dedup_threshold"] for prev in signatures):
                continue
            text = parent_text(row) if builder == "dedup-parent" else records[row]["text"]
            block_tokens = len(encoder.encode(passage_block(len(kept) + 1, records[row], text))) + 2
            if used + block_tokens > budget:
                continue
            kept.append(row)
            signatures.append(signature)
            texts.append(text)
            used += block_tokens
    blocks, citations = [], []
    for position, (row, text) in enumerate(zip(kept, texts), start=1):
        record = records[row]
        scenes = record.get("scenes") or []
        scene = f"Act {scenes[0][0]}, Scene {scenes[0][1]}" if scenes else "Unknown scene"
        blocks.append(passage_block(position, record, text))
        citations.append({
            "marker": position, "chunk_id": record["chunk_id"], "work": record["work"],
            "work_id": record["work_id"], "scene": scene, "speakers": record.get("speakers", []),
        })
    return {"context": "\n\n".join(blocks), "citations": citations}


@lru_cache
def _get_encoder():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def _generate(engine: _Engine, query: str, context_text: str, use_cache: bool = True) -> tuple[str, float]:
    params = engine.params
    deployment = engine.config["AZURE_OPENAI_CHAT_DEPLOYMENT"]
    user_message = f"Context:\n{context_text}\n\nQuestion: {query}" if params["uses_context"] else f"Question: {query}"
    key = hashlib.sha256(f"{deployment}|{params['contract']}|{params['max_completion_tokens']}|{user_message}".encode()).hexdigest()
    cache = engine.caches["generation-cache"] / (key + ".json")
    if use_cache and cache.is_file():
        cached = json.loads(cache.read_text())
        return cached["answer"], cached.get("latency_ms", 0.0)
    client = engine.get_client()
    started = time.perf_counter()
    response = _with_retry(lambda: client.chat.completions.create(
        model=deployment, max_completion_tokens=params["max_completion_tokens"],
        messages=[{"role": "system", "content": params["system_prompt"]}, {"role": "user", "content": user_message}]))
    latency_ms = (time.perf_counter() - started) * 1000
    answer = (response.choices[0].message.content or "").strip()
    cache.write_text(json.dumps({"answer": answer, "latency_ms": latency_ms}))
    return answer, latency_ms


def _retrieve_context(engine: _Engine, query: str) -> dict:
    primary, variants = _shape_query(engine, query)
    pool_size = engine.params["candidate_pool"]
    rankings = [_retrieve_pool(engine, variant, _embed(engine, variant), pool_size) for variant in variants]
    fused = rankings[0] if len(rankings) == 1 else _rrf(rankings, engine.params["rrf_k"], pool_size)
    if engine.params["reranker"] == "semantic":
        primary_vector = _embed(engine, primary)
        fused = sorted(fused, key=lambda row: _dot(primary_vector, engine.vectors[row]), reverse=True)
    return _build_context(engine, fused)


def answer(query: str, use_cache: bool = True) -> dict:
    """Online flow: query -> retrieve -> rerank -> context -> generate. Returns a grounded, cited answer."""
    query = (query or "").strip()
    if not query:
        raise ValueError("query must be a non-empty string")
    engine = get_engine()
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    built = _retrieve_context(engine, query)
    text, _ = _generate(engine, query, built["context"], use_cache=use_cache)
    abstained = engine.params["sentinel"] in text.upper()
    cited = {int(m) for m in _CITATION_PATTERN.findall(text)}
    used_citations = [c for c in built["citations"] if c["marker"] in cited]
    return {
        "request_id": request_id,
        "query": query,
        "answer": text,
        "citations": used_citations,
        "abstained": abstained,
        "latency_ms": (time.perf_counter() - started) * 1000,
    }


def _scene_label(record: dict) -> str:
    scenes = record.get("scenes") or []
    return f"Act {scenes[0][0]}, Scene {scenes[0][1]}" if scenes else "Unknown scene"


def answer_traced(query: str, use_cache: bool = True) -> dict:
    """Same online flow as ``answer`` but records what each stage produced, for the UI trace panel."""
    query = (query or "").strip()
    if not query:
        raise ValueError("query must be a non-empty string")
    engine = get_engine()
    params = engine.params
    request_id = uuid.uuid4().hex
    started = time.perf_counter()

    # Stage 09 - query handling: policy may rewrite or decompose the question.
    primary, variants = _shape_query(engine, query)
    primary_vector = _embed(engine, primary)

    # Stage 05 - retrieval: one ranking per variant, fused when there is more than one.
    pool_size = params["candidate_pool"]
    rankings = [_retrieve_pool(engine, v, _embed(engine, v), pool_size) for v in variants]
    fused = rankings[0] if len(rankings) == 1 else _rrf(rankings, params["rrf_k"], pool_size)

    def _brief(row: int, rank: int) -> dict:
        record = engine.records[row]
        return {"rank": rank, "work": record["work"], "scene": _scene_label(record),
                "speakers": record.get("speakers", [])[:4],
                "score": round(_dot(primary_vector, engine.vectors[row]), 3)}

    retrieved_rows = [_brief(row, i + 1) for i, row in enumerate(fused[:8])]

    # Stage 06 - reranking: reorder the fused pool only if a reranker is selected.
    reordered = False
    if params["reranker"] == "semantic":
        before = list(fused)
        fused = sorted(fused, key=lambda row: _dot(primary_vector, engine.vectors[row]), reverse=True)
        reordered = fused != before

    # Stage 07 - context building: dedup, parent context, token budget, citation assembly.
    built = _build_context(engine, fused)
    context_tokens = len(_get_encoder().encode(built["context"])) if built["context"] else 0

    # Stage 08 - generation: grounded answer under the selected contract.
    text, gen_latency = _generate(engine, query, built["context"], use_cache=use_cache)
    abstained = params["sentinel"] in text.upper()
    cited = {int(m) for m in _CITATION_PATTERN.findall(text)}
    used_citations = [c for c in built["citations"] if c["marker"] in cited]

    kept = len(built["citations"])
    if retrieved_rows:
        work_counts: dict[str, int] = {}
        for brief in retrieved_rows:
            work_counts[brief["work"]] = work_counts.get(brief["work"], 0) + 1
        top_work, top_n = max(work_counts.items(), key=lambda kv: kv[1])
        retrieval_note = f"{top_n} of {len(retrieved_rows)} top candidates from {top_work} (score ~{retrieved_rows[0]['score']})."
    else:
        retrieval_note = "No candidates retrieved for this query."
    if abstained and kept == 0:
        generation_note = "Abstained because no passages reached the context — nothing to ground an answer in."
    elif abstained:
        generation_note = (f"Abstained under the {params['contract']} contract even though {kept} passage(s) were in context: "
                           "the question is likely interpretive or not directly stated in the text, so the model refused to invent a claim.")
    else:
        generation_note = f"Answered from {len(used_citations)} cited passage(s)." if used_citations else "Answered from the retrieved context."

    stages = [
        {"stage": "09 Query Handling", "status": "ok",
         "fields": {"policy": params["policy"], "primary": primary,
                    "sub_queries": variants if len(variants) > 1 else []}},
        {"stage": "05 Retrieval", "status": "ok" if retrieved_rows else "warn",
         "note": retrieval_note,
         "fields": {"method": params["method"], "candidate_pool": pool_size, "returned": len(fused)},
         "rows": retrieved_rows},
        {"stage": "06 Reranking", "status": "ok",
         "fields": {"reranker": params["reranker"], "reordered": reordered}},
        {"stage": "07 Context Building", "status": "ok" if built["citations"] else "warn",
         "fields": {"builder": params["builder"], "token_budget": params["token_budget"],
                    "passages_kept": len(built["citations"]), "context_tokens": context_tokens},
         "rows": [{"marker": c["marker"], "work": c["work"], "scene": c["scene"],
                   "speakers": c.get("speakers", [])[:4]} for c in built["citations"]]},
        {"stage": "08 Generation", "status": "abstained" if abstained else "ok",
         "note": generation_note,
         "fields": {"contract": params["contract"], "latency_ms": round(gen_latency, 1),
                    "abstained": abstained, "cited_markers": sorted(cited) if cited else []}},
    ]

    return {
        "request_id": request_id,
        "query": query,
        "answer": text,
        "citations": used_citations,
        "abstained": abstained,
        "latency_ms": (time.perf_counter() - started) * 1000,
        "stages": stages,
    }


def retrieve_evidence(query: str, top_k: int = 5) -> dict:
    """Reusable retrieval tool: return the cited passages for a query without generating an answer."""
    query = (query or "").strip()
    if not query:
        raise ValueError("query must be a non-empty string")
    engine = get_engine()
    built = _retrieve_context(engine, query)
    return {"request_id": uuid.uuid4().hex, "query": query, "passages": built["citations"][:top_k],
            "context": built["context"]}


def build_offline_index() -> None:
    """Validate the prebuilt corpus index and warm the online engine.

    The heavy offline build (ingest -> chunk -> embed -> index) is executed by
    notebooks 01-04; this entry point verifies the artifact is present and
    hosted-backed, then warms the in-memory engine so the first request is fast.
    """
    get_engine()


# --------------------------------------------------------------------------- #
# Stage 12 - Operations & Safety: input guardrail and graceful degradation
# --------------------------------------------------------------------------- #
MAX_QUERY_CHARS = 2000   # reject oversized prompts at the boundary before any model call

# These patterns are LOGGED, not blocked: the strict grounding contract is the real defense against
# injection and exfiltration, so flagging is for monitoring, not for silently refusing a legitimate query.
_INJECTION_PATTERNS = {
    "override_instructions": re.compile(r"ignore (all |your |previous )?(instructions|rules|prompt)", re.IGNORECASE),
    "reveal_prompt": re.compile(r"(reveal|print|show|repeat|leak).{0,30}(system )?(prompt|instructions)", re.IGNORECASE),
    "role_switch": re.compile(r"you are now|act as|pretend to be|developer mode", re.IGNORECASE),
    "exfiltration": re.compile(r"(api[_ ]?key|secret|credential|token|password|\.env)", re.IGNORECASE),
}


def screen_query(query: str) -> dict:
    """Boundary guardrail: reject empty/oversized input; flag (never block) injection-shaped text for logging."""
    text = (query or "").strip()
    if not text:
        return {"ok": False, "reason": "empty_query", "flags": ["empty"]}
    if len(text) > MAX_QUERY_CHARS:
        return {"ok": False, "reason": "query_too_long", "flags": ["oversized"]}
    flags = [name for name, pattern in _INJECTION_PATTERNS.items() if pattern.search(text)]
    return {"ok": True, "reason": "ok", "flags": flags}


def safe_answer(query: str) -> dict:
    """Operations wrapper: screen input, then answer with graceful degradation on provider failure.

    Never raises for a provider error or a flagged query; returns a safe, abstaining response instead so a
    single failed upstream call cannot take the service down. Injection flags are attached for monitoring.
    """
    screen = screen_query(query)
    try:
        engine = get_engine()
    except Exception as exc:  # index artifact missing or Azure identity unavailable: degrade, do not crash
        return {"request_id": uuid.uuid4().hex, "query": query, "answer": "INSUFFICIENT_CONTEXT", "citations": [],
                "abstained": True, "degraded": True, "error": type(exc).__name__, "flags": screen.get("flags", [])}
    sentinel = engine.params["sentinel"]
    if not screen["ok"]:
        return {"request_id": uuid.uuid4().hex, "query": query, "answer": sentinel, "citations": [],
                "abstained": True, "degraded": True, "error": screen["reason"], "flags": screen["flags"]}
    try:
        result = answer(query)
        result["degraded"] = False
        result["flags"] = screen["flags"]
        return result
    except Exception as exc:  # provider outage, throttling past retries, etc.: degrade, do not crash
        return {"request_id": uuid.uuid4().hex, "query": query, "answer": sentinel, "citations": [],
                "abstained": True, "degraded": True, "error": type(exc).__name__, "flags": screen["flags"]}


def safe_answer_traced(query: str) -> dict:
    """Operations wrapper around ``answer_traced``: screens input and degrades gracefully, keeping the trace."""
    screen = screen_query(query)
    try:
        engine = get_engine()
    except Exception as exc:  # index artifact missing or Azure identity unavailable: degrade, do not crash
        return {"request_id": uuid.uuid4().hex, "query": query, "answer": "INSUFFICIENT_CONTEXT", "citations": [],
                "abstained": True, "degraded": True, "error": type(exc).__name__,
                "flags": screen.get("flags", []), "stages": []}
    sentinel = engine.params["sentinel"]
    if not screen["ok"]:
        return {"request_id": uuid.uuid4().hex, "query": query, "answer": sentinel, "citations": [],
                "abstained": True, "degraded": True, "error": screen["reason"],
                "flags": screen["flags"], "stages": []}
    try:
        result = answer_traced(query)
        result["degraded"] = False
        result["flags"] = screen["flags"]
        return result
    except Exception as exc:  # provider outage, throttling past retries, etc.: degrade, do not crash
        return {"request_id": uuid.uuid4().hex, "query": query, "answer": sentinel, "citations": [],
                "abstained": True, "degraded": True, "error": type(exc).__name__,
                "flags": screen["flags"], "stages": []}


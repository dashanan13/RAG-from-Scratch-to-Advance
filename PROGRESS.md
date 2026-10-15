# RAG-from-Scratch-to-Advance — Working Guide & Progress

> Read this FIRST before working on any notebook. It records what the project is,
> what's done, what's next, and the exact conventions to follow so I don't have to
> re-read the whole repo each time. Keep it updated after finishing a stage.

## What this project is
- Zero-to-production RAG system grounded over 10 Shakespeare plays.
- Pedagogical: each stage = one notebook in `experiments/` + one module in `production/`.
- Driving use case: "How do encounters with ghosts influence Hamlet and Macbeth?
  Compare their reactions with passages from both plays." Must cite real passages,
  separate fact from interpretation, and abstain when the corpus can't support an answer.
- Core principle: MEASURED decisions. Each notebook loads prior handoff, explains
  alternatives + trade-offs, runs controlled experiments, measures against labeled
  questions, picks the simplest option that clears thresholds, exports a handoff.

## Handoff / state model (IMPORTANT)
- Stages pass data via explicit JSON files in `.artifacts/`, NOT kernel state.
- Each notebook reads the PREVIOUS stage's handoff and writes its own.
- Notebooks must run top-to-bottom after a kernel restart (no hidden state).
- Shared `.env` at repo root is read by BOTH notebooks and `production/` — never drift.
- Fail loudly if an upstream artifact is missing (`raise RuntimeError("Run notebook XX first.")`).

## Progress status (update after each stage)
COMPLETE (detailed, ~18-36 cells, code + markdown):
- [x] 00 Foundations & Setup
- [x] 01 Ingestion & Parsing
- [x] 02 Chunking
- [x] 03 Embeddings
- [x] 04 Indexing
- [x] 05 Retrieval
- [x] 06 Reranking  (only notebook with execution outputs so far)

STUB (7 cells, markdown headers only — need full build-out):
- [ ] 07 Context Building
- [ ] 08 Grounded Generation
- [ ] 09 Query Handling & Adaptive RAG
- [ ] 10 Continuous Evaluation
- [ ] 11 Production & Serving
- [ ] 12 Operations & Safety

Production modules: currently mostly stubs that `raise NotImplementedError("Fill from experiments/XX.")`.
Fill a production module FROM its notebook once the notebook stage is finished/justified.

## Notebook <-> Production mapping
| # | Notebook | Production module(s) | Handoff artifact |
|---|---|---|---|
| 00 | 00-Foundations-and-Setup | settings.py, clients.py | setup-handoff.json |
| 01 | 01-Ingestion-and-Parsing | ingestion/parser.py (loaders, preprocess, pipeline) | ingestion-handoff.json |
| 02 | 02-Chunking | chunking/chunker.py | chunking-handoff.json |
| 03 | 03-Embeddings | embeddings/embedder.py | embeddings-handoff.json |
| 04 | 04-Indexing | indexing/indexer.py, indexing/vector_store.py | index.json |
| 05 | 05-Retrieval | retrieval/retriever.py, retrieval/hybrid_search.py | retrieval-handoff.json |
| 06 | 06-Reranking | retrieval/reranker.py | reranking-handoff.json |
| 07 | 07-Context-Building | retrieval/context_builder.py | context-handoff.json |
| 08 | 08-Grounded-Generation | generation/generator.py | generation-handoff.json |
| 09 | 09-Query-Handling-and-Adaptive-RAG | retrieval/query_processor.py | query-handoff.json |
| 10 | 10-Continuous-Evaluation | evaluation/dataset.py, evaluation/metrics.py | evaluation-results.json |
| 11 | 11-Production-and-Serving | api/main.py, api/routes.py, pipeline.py, tools/ | deployment-config.json |
| 12 | 12-Operations-and-Safety | api/, operations config | ops-config.json |

## Tech stack
- Python 3.10+ (`from __future__ import annotations` everywhere).
- Azure OpenAI: one chat deployment + one embedding deployment (hosted only, no local LLMs/GPUs).
- Auth: keyless Azure Entra identity (`DefaultAzureCredential` + bearer token provider). NEVER store account keys.
- Corpus + artifacts: Azure Blob Storage (accessed via `az` CLI, identity-based download).
- Retrieval built by hand in pure Python: Okapi BM25 keyword + dense vectors + hybrid RRF; IVF index.
- Telemetry: OpenTelemetry SDK + OTLP HTTP exporter + openinference OpenAI instrumentation -> Phoenix (docker-compose).
- Other libs: openai, tiktoken, python-dotenv, ipykernel, nbformat, nbstripout.
- Planned: FastAPI (stage 11). Possibly Azure AI Search later.

## Conventions — MARKDOWN cells (match this tone exactly)
- No emojis. Educational, conversational, addresses reader directly.
- Header hierarchy: `# NN - Stage Title`, then `## Why This Stage`, `### Concept`, `#### Sub-section`.
- Recurring section skeleton per complete notebook:
  1. Title + subtitle (e.g. "# 06 - Reranking" / "## Shakespeare Evidence Desk")
  2. "Why This Stage" — role in the RAG pipeline
  3. "Conceptual Foundations" — key terms, mental models, common misconceptions/failure modes
  4. "The Technique Landscape" — table comparing 4-6 alternatives (strengths / weaknesses / status)
  5. Numbered working sections: "1. Load the Previous Selection", "2. Explain the Alternatives",
     "3. Run Controlled Experiments", "4. Measure", "5. Select", "6. Export Handoff"
- Every stage includes a "## Metrics in This Stage — What Each Number Means" section placed
  right BEFORE the measurement/experiment step. It is a 4-column table: Metric | What it measures
  (which decision) | How it is computed (formula/code expr) | What it signifies (direction, caveats).
  Avoid raw '|' inside cells (breaks the table); word it out or escape. Added to notebooks 00-06.
- Heavy use of comparison tables and ASCII flow diagrams.
- Italic for *general concepts*, bold for **key terms**.
- ABBREVIATIONS: never use a short form without its full form. On first use write
  the full form followed by the abbreviation in parentheses, e.g.
  "Reciprocal Rank Fusion (RRF)", "Best Matching 25 (BM25)", "Inverted File index (IVF)".
  Applies to technique and metric names alike. After first use the short form is fine.
- Markdown cell ALWAYS precedes its code cell and fully explains: Purpose / What the code does /
  Fails loudly if... / Expected result. The code cell is then just the implementation.
- Be candid about failure modes and misconceptions; tie each decision back to the code and the metric.

## Conventions — CODE cells & production modules
- `from __future__ import annotations` at top.
- Module docstring: one line of purpose + where it maps (e.g. mentions `experiments/06`).
- Function/class docstrings: short, state the job. Not verbose.
- Inline comments explain WHY, not WHAT, and are sparse (explanations live in markdown cells).
  e.g. `# Work from the repository root so the notebook and the package read the same .env and artifacts.`
- Defensive checks documented and fail loudly with actionable messages.
- settings.py: `@dataclass(frozen=True) Settings` + `@lru_cache def get_settings()`.
- clients.py: `@lru_cache` singletons; lazy imports inside functions; token-provider auth.
- Production stubs: `raise NotImplementedError("Fill from experiments/XX.")` until the stage is done.
- No trailing/redundant comments; keep code clean.

## Workflow when building a STUB notebook (07-12)
1. Read this file + the target stub notebook + the PRIOR completed notebook for style.
2. Read the prior stage's handoff shape and the mapped production module stub.
3. Follow the markdown section skeleton above; keep tone/table/diagram conventions.
4. Load prior handoff -> explain alternatives -> controlled experiment -> measure vs
   eval-questions -> select simplest passing option -> export this stage's handoff.
5. After the notebook is solid, port the chosen implementation into the mapped production module.
6. Update the Progress checkboxes in this file.

## Pointers
- Repo root detection pattern: start from cwd; if `.env.example` is only in parent, use parent.
- Labeled eval questions live at `.artifacts/eval-questions.json`.
- Stage 06 enforces embedding backend == 'hosted' before running (guards against offline fallback).

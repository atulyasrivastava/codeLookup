# Code Lookup — Semantic Code Search

A semantic search engine for codebases. Instead of searching by exact keyword match, you ask a plain-English question and get back the most relevant functions/classes — built and evaluated against the [httpie/cli](https://github.com/httpie/cli) codebase.

## What it does

Type a question like `"where is the request timeout set"` and get back the actual function that handles it — even if none of your query's words literally appear in the code. This is powered by embedding-based semantic search, not keyword matching.

## How it works

**Ingestion pipeline** (offline, run once or whenever the source repo changes):

1. **target-repo** (httpie source code)
2. **extract.py** — Python's `ast` module parses each file and pulls out every function/class as a complete chunk (name, type, file, code, docstring). Output: `chunks.json`
3. **index.py** — each chunk is embedded via Ollama's `nomic-embed-text` model (code → 768-dim vector), then stored in Qdrant, a self-hosted vector database

**Query pipeline** (online, per request — coordinated by `orchestrator.py`):

4. **search.py** — the user's query is embedded the same way, then matched against stored vectors using cosine similarity to find the nearest (most semantically similar) code chunks
5. **Prompt-injection guard** (`sanitize_chunk` in `orchestrator.py`) — every retrieved chunk is scanned for suspicious instruction-like phrases before it's allowed anywhere near an LLM, since retrieved content — not just the user's query — can carry hidden instructions in RAG systems. Flagged chunks are marked, not silently dropped.
6. **generate.py** — the sanitized chunks plus the user's question are passed to a local LLM (Ollama's `codellama`) to produce a synthesized, plain-English answer, with retrieved code and the user's question kept in clearly separated, labeled sections of the prompt
7. **audit.py** — every query is logged (query text, retrieved results, scores, latency) as structured JSON Lines, so any request can be traced after the fact

Everything runs locally — no external API calls, no cost. A provider abstraction (`llm_provider.py`) is included, designed so the generation backend could be swapped to Azure OpenAI in an enterprise deployment without changing the pipeline itself.

## Setup & usage

Prerequisites: Python 3.10+, Docker, [Ollama](https://ollama.com) installed locally.

Step 1 — clone this repo and set up the environment:

    python -m venv venv
    Scripts\Activate.ps1        (Windows)
    source venv/bin/activate         (Mac/Linux)
    pip install -r requirements.txt

Step 2 — clone the target codebase to index:

    git clone https://github.com/httpie/cli.git target-repo

Step 3 — start Qdrant:

    docker run -d -p 6333:6333 qdrant/qdrant

Step 4 — pull the embedding model:

    ollama pull nomic-embed-text

Step 5 — extract code chunks:

    python extract.py

Step 6 — index into Qdrant:

    python index.py

Step 7 — search (retrieval only):

    python search.py how are HTTP headers parsed from command line arguments

Step 8 — pull the generation model:

    ollama pull codellama

Step 9 — run the full pipeline (retrieve, guard, generate, audit):

    python
    >>> from orchestrator import run
    >>> result = run("where is the request timeout set", top_k=3, should_generate=True)
    >>> print(result["answer"])

Indexed against `httpie/cli` at commit `5b604c37c6c67e18e7c3e9aee6c88a8c22b98345`.

## Evaluation

Extracted 638 chunks from the codebase (636 successfully embedded; 2 skipped due to embedding-server errors on unusually large classes — logged rather than crashing the pipeline).

Manually built a ground-truth set of 8 questions by reading the source and verifying the correct answer myself, then checked whether the correct function appeared in the top-3 search results:

| # | Query | Correct answer | Top-3 hit? |
|---|---|---|---|
| 1 | How are HTTP headers parsed from command line arguments | `headers` (sessions.py) | Yes |
| 2 | Where is the request timeout set | `make_send_kwargs` | Yes |
| 3 | How does httpie handle authentication credentials | `HTTPBasicAuth` | Yes |
| 4 | How is JSON response output colored | `get_color` | No (ranked #4) |
| 5 | How are cookies saved between requests | `cookies` (getter/setter) | Yes |
| 6 | How does httpie download a file to disk | `Downloader` | Yes |
| 7 | How is the response body pretty printed | `format_body` | Yes |
| 8 | How are plugins loaded and registered | `register` | Yes |

**Result: 7/8 (87.5%) top-3 accuracy.**

The one miss (#4) is informative: match scores were noticeably lower and more tightly clustered than in successful queries (0.56–0.58 vs. 0.6–0.7), suggesting the embedding model itself had low confidence — a signal that could be used to flag low-quality results at query time in a production version.

## Generation (retrieval-augmented answers)

Beyond returning ranked code chunks, the system can optionally synthesize a plain-English answer using a local LLM (`codellama` via Ollama), grounded in the retrieved, sanitized chunks.

Example — query: *"where is the request timeout set"*

The system correctly identified `make_send_kwargs` (the actual answer) and explained the `args.timeout` logic accurately, grounded in the top-ranked retrieved chunk. However, it also introduced a class name (`RequestsAuthBase`) that did not appear anywhere in the retrieved context — a real, observed hallucination, not a hypothetical one. This is a known, unsolved failure mode in RAG systems generally: retrieval can be correct while generation still drifts from the provided context. It's flagged here deliberately rather than glossed over, since recognizing *when* generation isn't fully grounded is arguably as important as the generation working at all.

## Orchestration, auditing & prompt-injection handling

Added after identifying these as gaps, to move the project closer to what a production/enterprise deployment would actually require:

- **Orchestrator** (`orchestrator.py`) — coordinates the query-time pipeline (retrieve → guard → generate → audit) as explicit stages, each with its own error handling, so a failure in one stage (e.g., the generation model being unavailable) doesn't take down the whole request — the system still returns retrieved results even if generation fails.
- **Auditing** (`audit.py`) — every query is logged in JSON Lines format (query, retrieved chunks, scores, latency, timestamp), enabling debugging, compliance-style traceability, and pattern analysis over time (e.g., spotting queries that consistently score low).
- **Prompt-injection guard** — retrieved chunks are scanned for suspicious instruction-like phrases before reaching the LLM, since in RAG systems the retrieved content — not the user's query — is the more realistic injection vector. Covered by unit tests (`test_injection.py`) checking both true positives (catches injection attempts) and true negatives (doesn't over-flag legitimate code) — including a known limitation that substring matching can false-positive on innocent mentions of flagged phrases (e.g., a docstring genuinely describing a "system prompt" feature).

## Limitations & what I'd add next

- **Pure vector search, no hybrid layer.** Combining with keyword/BM25 search would catch exact-name matches that embeddings sometimes miss.
- **No re-ranking step.** A cross-encoder re-ranker on the top-k candidates would likely improve precision, especially for queries like #4.
- **Small eval set.** 8 hand-verified questions is a starting point, not a robust benchmark — a real system would need 50+.
- **No caching.** Repeated/similar queries currently re-embed from scratch.
- **Not containerized end-to-end yet.** Qdrant runs in Docker; the app itself doesn't. A `docker-compose.yml` bundling both would make this properly one-command-deployable.
- **Robust injection detection.** Current guard is substring-based; a real system needs an LLM-based classifier judging intent, or structural separation of instructions from retrieved content (e.g., via tool-use APIs), rather than phrase matching.
- **Grounding checks on generated answers.** The system doesn't currently verify that generated text is fully supported by retrieved context — the observed hallucination above wasn't caught automatically.
- **Rate limiting and auth.** No protection currently against abuse if this were exposed as a real service.
- **Monitoring/alerting on the audit log.** Logging exists, but nothing currently watches it for anomalies (latency spikes, unusual flag rates, etc.).

## Stack

Python, Qdrant (vector DB), Ollama (local embeddings — `nomic-embed-text` — and generation — `codellama`), Python `ast` module for code parsing. Fully self-hosted, zero API cost.
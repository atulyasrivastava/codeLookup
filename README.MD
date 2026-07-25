# Code Lookup — Semantic Code Search

A semantic search engine for codebases. Instead of searching by exact keyword match, you ask a plain-English question and get back the most relevant functions/classes — built and evaluated against the [httpie/cli](https://github.com/httpie/cli) codebase.

## What it does

Type a question like `"where is the request timeout set"` and get back the actual function that handles it — even if none of your query's words literally appear in the code. This is powered by embedding-based semantic search, not keyword matching.

## How it works

Pipeline, top to bottom:

1. **target-repo** (httpie source code)
2. **extract.py** — Python's `ast` module parses each file and pulls out every function/class as a complete chunk (name, type, file, code, docstring). Output: `chunks.json`
3. **index.py** — each chunk is embedded via Ollama's `nomic-embed-text` model (code → 768-dim vector), then stored in Qdrant, a self-hosted vector database
4. **search.py** — a query is embedded the same way, then matched against stored vectors using cosine similarity to find the nearest (most semantically similar) code chunks

Everything runs locally — no external API calls, no cost.

## Setup & usage

Prerequisites: Python 3.10+, Docker, [Ollama](https://ollama.com) installed locally.

Step 1 — clone this repo and set up the environment:

    python -m venv venv
    venv\Scripts\Activate.ps1        (Windows)
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

Step 7 — search:

    python search.py how are HTTP headers parsed from command line arguments

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

## Limitations & what I'd add next

- **Pure vector search, no hybrid layer.** Combining with keyword/BM25 search would catch exact-name matches that embeddings sometimes miss.
- **No re-ranking step.** A cross-encoder re-ranker on the top-k candidates would likely improve precision, especially for queries like #4.
- **Small eval set.** 8 hand-verified questions is a starting point, not a robust benchmark — a real system would need 50+.
- **No caching.** Repeated/similar queries currently re-embed from scratch.
- **Not containerized end-to-end yet.** Qdrant runs in Docker; the app itself doesn't. A `docker-compose.yml` bundling both would make this properly one-command-deployable.

## Stack

Python, Qdrant (vector DB), Ollama (local embeddings — `nomic-embed-text`), Python `ast` module for code parsing. Fully self-hosted, zero API cost.
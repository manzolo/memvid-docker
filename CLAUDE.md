# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Dockerized wrapper around [Memvid](https://pypi.org/project/memvid/), which encodes text chunks as QR codes inside an MP4 video for compact, semantically-searchable storage. This repo adds:

- A document-ingestion pipeline (Markdown + PDF → `knowledge.mp4` + `knowledge_index.json`)
- A Flask web UI on port 7860 with two answering modes
- Optional Ollama integration on the Docker host for LLM-based answer synthesis

## Common commands

All workflows go through `docker compose` via the Makefile:

```bash
make start     # docker compose up -d
make stop      # down + rm
make restart   # down + rm + up + follow logs
make rebuild   # docker compose build
make logs      # follow logs
```

The compose `command:` runs `python /app/process_docs.py ui`, which:
1. Ingests every `.md` in `/app/docs` and `.pdf` in `/app/pdfs`
2. Builds `output/knowledge.mp4` + `output/knowledge_index.json`
3. Starts Flask on `0.0.0.0:7860`

To rebuild the knowledge video without the UI: `docker compose run --rm memvid python /app/process_docs.py`.

To run the smoke test inside the container: `docker compose run --rm memvid python /app/test_memvid.py`.

There is no test runner, linter, or formatter configured.

## Architecture

### Two Flask entry points — only one is wired up
- `py/process_docs.py` (the live entry point, run as `process_docs.py ui`): combines document ingestion *and* the web server in one process. Routes: `/`, `/ask`, `/status`. Template: `templates/index.html`.
- `py/chat.py` (standalone, not invoked by docker-compose): assumes `output/knowledge.mp4` already exists. Routes: `/`, `/api/chat`, `/api/status`. Template: `templates/chat.html`.

When changing chat behavior, edit `process_docs.py` — `chat.py` is dead code from an earlier split unless you rewire compose.

### Answer modes (in `process_docs.py`)
`/ask` accepts `mode`:
- `mechanical` → raw `MemvidChat.chat()` output, no LLM
- `intelligent` (default) → raw chunks passed through `clean_context()` (strips Memvid's "Based on the knowledge base..." prefixes, keeps top-3 chunks ≥20 chars) then sent to Ollama with a strict Italian prompt at `temperature=0.1`. Falls back to cleaned raw if Ollama is unreachable.

### Ollama wiring
- Host configured via `OLLAMA_HOST` env (compose default: `http://172.17.0.1:11434` — the Docker bridge gateway, i.e. Ollama running on the host machine, *not* inside compose).
- Model via `OLLAMA_MODEL` (default `llama3`).
- Connection probed via `GET /api/tags` before every synthesis call; failure degrades gracefully to raw chunks.

### Volumes & data flow
Compose mounts:
- `./docs:/app/docs:ro` — Markdown source (read-only)
- `./pdfs:/app/pdfs:ro` — PDF source (read-only)
- `./output:/app/output` — generated MP4 + index
- `./data:/app/data` — `HF_HOME` cache for sentence-transformers/HuggingFace models

The container runs as non-root `appuser` (UID 1000). If host file ownership doesn't match, ingestion will fail to write to `output/` or `data/`.

### Gotcha: ingestion on every UI start
`launch_ui()` re-runs `process_docs()` on every container start and `sys.exit(1)` if no `.md`/`.pdf` is found. The existing `output/knowledge.mp4` is overwritten each time — there is no incremental indexing. The Dockerfile only copies `*.py` from `py/` and `templates/`; code changes require `make rebuild`.

### .docx is not supported
`docs/` contains a `.docx` file but `process_docs()` only matches `.endswith(".md")`. The `.docx` is silently ignored.

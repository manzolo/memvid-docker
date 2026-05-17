# memvid-docker

[![CI](https://github.com/manzolo/memvid-docker/actions/workflows/ci.yml/badge.svg)](https://github.com/manzolo/memvid-docker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Dockerized wrapper around [Memvid](https://pypi.org/project/memvid/) that ingests your Markdown and PDF documents, encodes them as QR codes inside a single MP4 file, and serves a web UI that answers questions over them — optionally synthesizing answers through a local [Ollama](https://ollama.com) model.

## How it works

```
docs/*.md  ─┐
            ├─► MemvidEncoder ─► output/knowledge.mp4 + knowledge_index.json
pdfs/*.pdf ─┘                              │
                                           ▼
                                    MemvidChat (semantic search over QR-encoded chunks)
                                           │
                  ┌────────────────────────┴────────────────────────┐
                  │                                                 │
            mechanical mode                                  intelligent mode
            (raw chunks)                                     (Ollama on the host
                                                              synthesizes an answer)
```

The Flask UI on `:7860` exposes both modes; mode is selected per-request.

## Quick start

```bash
# Drop documents to ingest into ./docs (Markdown) and ./pdfs (PDF)
make start          # docker compose up -d
make logs           # follow ingestion + server logs
# open http://localhost:7860
```

Ingestion runs on every container start and overwrites `output/knowledge.mp4`. There is no incremental indexing.

### Makefile targets

| Command | What it does |
|---|---|
| `make start` | `docker compose up -d` |
| `make stop` | `down` + `rm -f` |
| `make restart` | `stop` then `start` and tail logs |
| `make rebuild` | `docker compose build` |
| `make logs` | `docker compose logs -f` |

After editing anything under `py/` or `templates/`, run `make rebuild` — the Dockerfile bakes them in at build time.

## Configuration

Environment variables (set in `docker-compose.yml`):

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://172.17.0.1:11434` | Ollama endpoint. Default targets the Docker bridge gateway, i.e. an Ollama running on the **host machine**, not in compose. |
| `OLLAMA_MODEL` | `llama3` | Model name passed to `/api/generate`. |
| `HF_HOME` | `/app/data/.cache` | Cache dir for sentence-transformers downloads. |

If Ollama is unreachable, `intelligent` mode degrades gracefully to a cleaned version of the raw Memvid chunks.

## HTTP API

| Route | Method | Body | Returns |
|---|---|---|---|
| `/` | GET | — | UI (`templates/index.html`) |
| `/ask` | POST | `{"question": "...", "mode": "intelligent"\|"mechanical"}` | `{"answer", "mode", "response_type"}` |
| `/status` | GET | — | `{"memvid_ready", "ollama_available", "ollama_host", "ollama_model"}` |

## Volume layout

| Host path | Container path | Mode | Purpose |
|---|---|---|---|
| `./docs` | `/app/docs` | ro | Markdown sources (only `*.md` is matched — `.docx` is ignored) |
| `./pdfs` | `/app/pdfs` | ro | PDF sources |
| `./output` | `/app/output` | rw | Generated MP4 + JSON index |
| `./data` | `/app/data` | rw | HuggingFace model cache |

The container runs as non-root `appuser` (UID 1000). Host directories must be writable by that UID.

## Limitations

- **No incremental indexing.** Every UI start re-ingests everything in `docs/` + `pdfs/` and overwrites the video.
- **Only `.md` and `.pdf`.** A `.docx` left under `docs/` is silently skipped.
- **Ingestion is mandatory.** If `docs/` and `pdfs/` are both empty, the container exits with code 1.
- **`py/chat.py` is dead code.** An earlier standalone server, not wired up by compose. Edit `py/process_docs.py` instead.

## Development

There is no separate Python test suite. CI (see `.github/workflows/ci.yml`) runs two jobs:

**`validate`** (fast, ~30s):
- Python syntax (`py_compile`) of every file under `py/`
- `docker compose config` parses cleanly
- Dockerfile passes [hadolint](https://github.com/hadolint/hadolint)
- Required files referenced by `Dockerfile` / `docker-compose.yml` exist

**`integration`** (slow, ~10 min cold / ~3 min cached):
- Builds the Docker image (cached via `type=gha`)
- Spins up `ollama/ollama` and pulls `tinyllama`
- Ingests a sample Markdown doc, waits for `/status` to report ready
- Hits `/ask` in both `mechanical` and `intelligent` modes and asserts the response shape

A smoke test against Memvid itself lives in `py/test_memvid.py` and can be run inside the container:

```bash
docker compose run --rm memvid python /app/test_memvid.py
```

## License

[MIT](LICENSE) — do whatever you want, just keep the copyright notice.

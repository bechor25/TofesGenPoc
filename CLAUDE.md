# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

TofesGenPoc (`doc2tests`) turns any Israeli form (image / PDF / Word) into many
realistic copies with **other people's** data. Flow: understand the document → decide
which values are personal → generate coherent, validated fake data → edit the ORIGINAL
image in place with `gpt-image-2`, replacing only personal values while preserving the
exact form design. Everything is generated; nothing real is leaked.

## Pipeline (the mental model)

```
file (image/pdf/word)
  → rasterize            ingest/rasterize.py      → page PNG(s)
  → grounded extract     ingest/grounded.py       → two vision passes:
       pass 1 TRANSCRIBE every text line + bbox
       pass 2 UNDERSTAND (the "understanding agent"): doc summary + per field
              {label, value, personal?, type, slot}   (content-based, NOT label keywords)
  → detect               deid/detect.py           → DetectedValue[] (LLM type wins;
                                                     deid/classify.py regex = fallback)
  → review gate          human confirms/edits in the UI  (LangGraph interrupt_before)
  → generate data        generate/population.py    → N coherent variants:
       free-text (diagnosis/reason/…) → generate/data_agent.py  (realistic LLM text)
       structured (id/date/phone/…)   → generate/strategies.py  (local + VALIDATED)
       same `slot` → one shared value (a recipient printed twice stays identical)
  → render image ON DEMAND  imagegen/edit.py + providers/openai_provider.py
       gpt-image-2 edits the original per chosen variant (EXPENSIVE, metered)
```

Orchestration: `orchestrator/graph.py` (LangGraph, data-only — never renders images),
`orchestrator/batch.py` (scale over many files + on-demand `render_variant`).
API + UI: `api/` (FastAPI — JSON + SSE over the same stages; background jobs stream live
status from the log buffer) serves `frontend/` (React SPA: Vite/TS/Tailwind, RTL Hebrew,
single/batch/archive). Persistence: `db/` (sources → generated images).

## Commands

```bash
# Everything runs on Docker (see "Docker" below) — this is the intended way to run.
docker compose up --build           # postgres (db) + FastAPI/React app on :8501

# Backend dev checks (run before finishing any change — all three must pass):
uv run pytest -q --ignore=tests/orchestrator/test_live_e2e.py \
                 --ignore=tests/extraction/test_live_openai.py   # skip PAID live tests
uv run mypy src                     # strict
uv run ruff check src tests
uv run ruff check --fix src tests   # autofix (imports, etc.)

uv add <pkg>                        # add a dependency (updates uv.lock)

# Frontend (React SPA in frontend/):
cd frontend && npm install
npm run dev      # Vite dev server; proxies /api -> uvicorn on :8501
npm run build    # tsc typecheck + vite build -> frontend/dist (served by FastAPI)
npm run test     # vitest

# Run the API alone (dev, without Docker): uv run uvicorn doc2tests.api:app --port 8501
```

Run tests for one area: `uv run pytest tests/generate -q`.

**Live tests cost money.** `tests/conftest.py` loads `.env`, so `tests/extraction/
test_live_openai.py` and `tests/orchestrator/test_live_e2e.py` make REAL OpenAI calls
when `OPENAI_API_KEY` is set — the latter even renders a paid gpt-image-2 image. Exclude
both in the dev loop (see the pytest command above).

## Conventions

- Python 3.12, **uv** for deps, **Pydantic v2** contracts (`contracts/`), **LangGraph**,
  **SQLAlchemy 2.0**. TDD; **mypy strict**; **ruff** (line length 100).
- Match surrounding style. Node functions convert errors to `StageError` in state rather
  than raising across the graph boundary.
- **Field typing is dynamic**: the model assigns each value's `type` by content. Never
  reintroduce brittle label-keyword matching as the primary path (it is only a fallback).
- Two agents share the extraction call, not a chain of narrow ones: the *understanding
  agent* (`ingest/grounded.py`) does summary + personal? + type + slot; the *data agent*
  (`generate/data_agent.py`) writes realistic free-text. Both degrade gracefully.
- Every pipeline stage logs per-field (`common/logging.py` buffer → UI "לוגים" panel +
  the "אבחון" diagnostics table). Keep that observability when editing stages.

## Providers & models (`.env`, gitignored)

- `OPENAI_API_KEY` — real key, **never commit or echo it**. Only `.env.example` is tracked.
- `OPENAI_VISION_MODEL=gpt-5.1` — extraction (full resolution; do not downscale).
- `OPENAI_IMAGE_MODEL=gpt-image-2` — image edit. gpt-image-2 rejects `input_fidelity`
  (sent only for gpt-image-1/1.5). Best when the replacement set is SMALL.
- `DATABASE_URL` — `postgresql+psycopg://…` in compose; `sqlite:///…` works too. Unset =
  persistence off (app still runs).

## Docker

`docker-compose.yml`: `db` (postgres:16) + `app` (built from `Dockerfile`, LibreOffice
for Word). The app's `DATABASE_URL` is overridden to the compose Postgres; `OPENAI_API_KEY`
comes from `.env` via `env_file`. Volume `pgdata` persists the archive.

## Cost & safety

- **Image generation is expensive** — never render without an explicit reason; it is
  on-demand and metered by design (`render_variant`, the "רנדר" buttons). Data generation
  is cheap and runs freely.
- Generated data must be VALID (Israeli id checksum, dates, phone, …) and must read as
  real Hebrew — never faker lorem-ipsum for descriptions.
- `.env` holds the real key and is gitignored. Never commit it or print its contents.

## Layout

`ingest/` rasterize + grounded extract · `deid/` detect + classify · `generate/` data ·
`imagegen/` image edit · `orchestrator/` graph + batch + config · `providers/` OpenAI/Ollama ·
`contracts/` Pydantic state/enums · `db/` models + repo · `api/` FastAPI (jobs/SSE, routes,
workspace) · `frontend/` React SPA · `ui/helpers.py` (records→rows, zip; reused by the API) ·
`validators/` Israeli validators · `common/` logging/json/slug.

Note: `coverage/`, `render/`, `schema/`, `template/` are legacy from the pre-pivot design
and are not part of the image-edit pipeline — prefer the modules above.

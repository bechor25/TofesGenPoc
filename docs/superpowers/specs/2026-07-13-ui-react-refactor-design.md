# UI Refactor: Streamlit → FastAPI + React SPA

**Date:** 2026-07-13
**Status:** Approved (design)
**Branch:** `feat/react-ui-refactor`

## Goal

Replace the Streamlit UI (`ui/app.py`) with a self-built, high-quality UI:
a **FastAPI** JSON+SSE backend and a **React (Vite + TypeScript + Tailwind)**
single-page app. Fresh, modern, clean design — sidebar navigation, central
workspace, cards, light/dark toggle, native RTL Hebrew (no CSS hacks layered on
top of a framework we don't control).

**Hard constraint:** nothing in the existing pipeline breaks. The data pipeline
(`ingest → detect → generate → render`) stays untouched; tests run at every step.

## Non-goals

- No change to extraction quality, models, prompts, or the pipeline logic.
- No change to the DB schema / persistence (`db/`).
- No LangGraph in the API path (the API calls the stage functions directly, the
  same way `orchestrator/batch.py` already does). `graph.py` stays for tests.

## Feature parity (must keep all of it)

**Single flow:** upload (jpg/png/pdf/docx) → live extraction status → review
table (label, value, `field_type` select, `is_personal`, `slot`/קישור; add rows;
pick N) → generate data → per-variant render table with a "יצירת טופס" checkbox +
render selected / render all → diagnostics table (per-field end-to-end) + gallery
+ zip download.

**Batch flow:** many files, N per file + parallel workers → per-file result cards
with the same render table.

**Archive flow:** sources (unique id + summary) → generated variants → view /
download image + values.

**Cross-cutting:** real-time stage + elapsed status (from the log buffer), an
end-to-end logs panel, DB persistence on render.

## Architecture

```
frontend/                         Vite React TS + Tailwind (RTL)  ──build──► dist/
  src/                                                                         │
    api/         fetch + SSE client, TanStack Query hooks                      │ served static
    store/       Zustand (workspace id, UI, theme)                             │ by FastAPI
    components/  AppShell, UploadZone, Stepper, LiveStatus, ReviewTable,       ▼
                 VariantsTable, Gallery, Diagnostics, Archive, LogsPanel
    views/       SingleView, BatchView, ArchiveView

src/doc2tests/api/                FastAPI backend
  app.py         create_app(): routes + mounts dist/ as static
  jobs.py        in-process JobManager (thread + per-job log marker + SSE generator)
  workspace.py   WorkspaceStore: doc_id -> {page_image, detected, doc_summary,
                                            population, rendered images}
  schemas.py     Pydantic v2 request/response models
  status.py      _STATUS_MAP moved here (log line -> Hebrew stage), used by SSE
  deps.py        provider builders / store singletons (DI)
```

The API is a thin layer over existing code:
- `ingest_parse`, `detect_fields`, `generate_population`, `render_variant`
  (from `ingest/`, `deid/`, `generate/`, `orchestrator/batch.py`) — unchanged.
- Review = override `detected` with the user-edited values before
  `generate_population` (exactly what `review_gate` does today).
- `ui/helpers.py` (`records_to_rows`, `zip_images`) is reused by the API.

### State model

Server-side **in-memory `WorkspaceStore`**, keyed by an ephemeral `doc_id`.
Holds the heavy working artifacts across steps: page-image bytes, `detected`,
`doc_summary`, `population`, and rendered images. This mirrors today's Streamlit
`session_state` but on the server. Lost on restart — acceptable (Streamlit lost
it too); durable output is persisted to the DB on render, as it is now.

### Jobs + realtime (SSE)

Extraction can take minutes (gpt-5.1). Blocking HTTP would time out / feel dead.
So slow work runs as an **async job**:

1. `POST` (extract / generate / render / batch) starts a background thread,
   returns `{ job_id }` immediately (and `doc_id` for extract).
2. `GET /api/jobs/{job_id}/events` is an **SSE** stream. Each ~0.4s the server
   reads job status + `logs_since(marker)`, maps the latest line to a Hebrew
   stage (`status.py`), and pushes `{stage, elapsed, progress?}`. On completion
   it pushes `{done:true, result}` or `{error}`.

Reuses the existing `common/logging.py` buffer (`log_marker`, `logs_since`,
`recent_logs`) — no logging changes.

## API surface

| Method + path | Purpose | Returns |
|---|---|---|
| `POST /api/extract` (multipart) | start extract job | `{job_id, doc_id}` |
| `GET  /api/jobs/{id}/events` (SSE) | live status | `stage/elapsed …`, then `done+result` or `error` |
| `GET  /api/docs/{doc_id}` | reviewed-doc data | `detected[]`, `doc_summary`, `page_image_url` |
| `POST /api/docs/{doc_id}/generate` | reviewed values + N → population | `{job_id}` |
| `POST /api/docs/{doc_id}/render` | variant index → gpt-image-2 | `{job_id}` (metered) |
| `POST /api/batch` (multipart) | many files + N + workers | `{job_id}` → per-file results |
| `GET  /api/sources` | archive list | sources + counts |
| `GET  /api/sources/{id}/generated` | variants for a source | generated rows |
| `GET  /api/image/{kind}/{id}` | serve image bytes | png |
| `GET  /api/logs?n=400` | logs panel | text lines |

## Frontend

- **Vite + React + TypeScript + Tailwind**, `dir="rtl"`, Tailwind logical
  properties; light/dark theme persisted to `localStorage`.
- **State:** TanStack Query for server state + mutations + job polling/SSE;
  a small **Zustand** store for the active `doc_id`, view, and theme.
- **Views:** `Single`, `Batch`, `Archive` behind a sidebar nav.
- **Components:** `AppShell` (sidebar + header + theme toggle), `UploadZone`,
  `Stepper`, `LiveStatus` (SSE consumer: stage + elapsed + progress), `ReviewTable`
  (editable rows, add row, type select, personal checkbox, slot), `VariantsTable`
  (per-variant "יצירת טופס" checkbox + render selected/all), `Gallery` (+ zip),
  `Diagnostics`, `Archive`, `LogsPanel`.

## Docker

Multi-stage `Dockerfile`:
1. `node:20` — `npm ci && npm run build` in `frontend/` → `dist/`.
2. `python:3.12-slim` (as today, with LibreOffice) — copy `dist/`, `uv sync`,
   `CMD uvicorn doc2tests.api.app:app --host 0.0.0.0 --port 8501`.

`docker-compose.yml` port mapping (8501) unchanged. Deps: **remove** streamlit;
**add** `fastapi`, `uvicorn[standard]`, `python-multipart`. `.dockerignore` keeps
`frontend/node_modules` and `frontend/dist` out of the Python context.

## Testing (run continuously — the user's explicit requirement)

- **Backend:** `pytest` + FastAPI `TestClient`, reusing existing provider stubs.
  Cover: extract job → doc data, generate, render (stubbed image), batch, archive,
  the `JobManager`, the `WorkspaceStore`, and the SSE event generator (tested as a
  plain generator function). `mypy --strict` on `src/doc2tests/api`. `ruff` clean.
- **Frontend:** Vitest + React Testing Library for `ReviewTable` (edit/add/type)
  and `VariantsTable` (selection → render targets).
- **Existing pipeline tests:** unchanged and must stay green throughout.
- **Gate:** after every phase, `uv run pytest -q && uv run mypy src && uv run ruff
  check src tests` must pass before moving on.

## Migration / removal

- Delete `src/doc2tests/ui/app.py` and `.streamlit/`; remove the `streamlit` dep.
- Keep `ui/helpers.py` (reused by the API).
- Backend pipeline modules untouched. `graph.py` kept (tests / optional).

## Rollout order (each phase ends green)

1. Design spec (this doc).
2. FastAPI backend package + deps + backend tests.
3. React scaffold (Vite/TS/Tailwind/RTL/theme) + API client.
4. Components + views (parity with every Streamlit feature).
5. Frontend tests.
6. Docker multi-stage + compose + remove Streamlit.
7. Full end-to-end verify in docker-compose.

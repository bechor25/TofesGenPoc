# React UI Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit UI with a FastAPI (JSON + SSE) backend and a React (Vite/TS/Tailwind) SPA, at full feature parity, without breaking the existing pipeline.

**Architecture:** A thin FastAPI layer wraps the *unchanged* pipeline stage functions (`ingest_parse → detect_fields → generate_population → render_variant`). Slow work runs as in-process background jobs; the UI streams live status over SSE from the existing log buffer. A server-side in-memory `WorkspaceStore` holds working artifacts across steps. The React SPA serves a fresh, clean, RTL design.

**Tech Stack:** FastAPI, uvicorn, python-multipart, Pydantic v2, SSE; React 18, Vite, TypeScript, Tailwind, TanStack Query, Zustand, Vitest.

**Green gate (every task):** `uv run pytest -q && uv run mypy src && uv run ruff check src tests` must pass. Frontend tasks additionally: `npm run build && npm run test` inside `frontend/`.

---

## Phase A — Backend (FastAPI)

### Task A1: Add deps, create `api/` package skeleton

**Files:**
- Modify: `pyproject.toml` (add `fastapi`, `uvicorn[standard]`, `python-multipart`; add `httpx` to dev for TestClient)
- Create: `src/doc2tests/api/__init__.py`
- Test: `tests/api/test_app.py`

- [ ] Add deps: `uv add fastapi "uvicorn[standard]" python-multipart` and `uv add --dev httpx`.
- [ ] Write failing test: `GET /api/health` returns `{"status":"ok"}`.
- [ ] Implement `create_app()` in `api/app.py` with a health route.
- [ ] Green gate. Commit.

### Task A2: `schemas.py` — request/response contracts

**Files:** Create `src/doc2tests/api/schemas.py`; Test `tests/api/test_schemas.py`

Pydantic v2 models:
- `DetectedDTO {id,label,value,field_type:str,is_personal:bool,slot:str|None}`
- `DocDataDTO {doc_id,doc_summary,detected:list[DetectedDTO],page_image_url:str|None}`
- `ReviewedValueDTO {label,value,field_type,is_personal,slot}` and `GenerateReq {values:list[ReviewedValueDTO], n:int}`
- `RenderReq {variant_index:int}`
- `JobRef {job_id:str, doc_id:str|None=None}`
- `VariantDTO {index:int, values:dict[str,str], rendered:bool}`
- `SourceDTO`, `GeneratedDTO` mirroring `repo` rows.

- [ ] Test: round-trip a `DetectedDTO` from a `DetectedValue` via a `from_detected` classmethod.
- [ ] Implement models + `from_detected`/`to_detected` mappers.
- [ ] Green gate. Commit.

### Task A3: `workspace.py` — in-memory store

**Files:** Create `src/doc2tests/api/workspace.py`; Test `tests/api/test_workspace.py`

```python
@dataclass
class Workspace:
    doc_id: str
    filename: str
    page_image: bytes | None = None
    detected: list[DetectedValue] = field(default_factory=list)
    doc_summary: str = ""
    population: list[Record] = field(default_factory=list)
    rendered: dict[int, bytes] = field(default_factory=dict)
    source_id: int | None = None

class WorkspaceStore:
    def new(self, filename: str) -> str: ...          # returns doc_id (uuid-free: counter)
    def get(self, doc_id: str) -> Workspace: ...        # raises KeyError -> 404 in route
    def as_document_result(self, doc_id) -> DocumentResult: ...
```

Note: `Date.now`/`uuid` fine here (runtime, not a workflow script). doc_id = `f"doc-{n}"` from an incrementing counter under a lock (deterministic, testable).

- [ ] Test: `new` then `get` returns the same workspace; `get` unknown raises `KeyError`.
- [ ] Test: `as_document_result` builds a `DocumentResult` with page_image + detected + population.
- [ ] Implement. Green gate. Commit.

### Task A4: `status.py` — log line → Hebrew stage

**Files:** Create `src/doc2tests/api/status.py`; Test `tests/api/test_status.py`

Move `_STATUS_MAP` (from the old `ui/app.py`) here as `STATUS_MAP`, plus:
```python
def friendly_stage(lines: list[str]) -> str:
    for line in reversed(lines):
        msg = line.split("|", 1)[-1].strip().lower()
        for key, heb in STATUS_MAP:
            if key in msg:
                return heb
    return ""
```

- [ ] Test: a line containing `"grounded transcribe: ..."` → `"מתעתק כל טקסט מהמסמך"`; empty list → `""`.
- [ ] Implement. Green gate. Commit.

### Task A5: `jobs.py` — JobManager + SSE generator

**Files:** Create `src/doc2tests/api/jobs.py`; Test `tests/api/test_jobs.py`

```python
@dataclass
class Job:
    id: str
    marker: int
    status: str = "running"        # running | done | error
    result: Any = None
    error: str | None = None
    started: float = 0.0

class JobManager:
    def start(self, fn: Callable[[], Any]) -> str:      # spawns daemon thread, captures log_marker()
    def get(self, job_id: str) -> Job:
    def events(self, job_id: str) -> Iterator[str]:     # yields SSE 'data: {json}\n\n' until done/error
```

`events` loop: while running → yield `{stage: friendly_stage(logs_since(marker)), elapsed}` every ~0.4s; on done → yield `{done:true, result}`; on error → yield `{error}`. Convert result to JSON-safe payload via a callback the route supplies (keep JobManager generic — result is opaque; route serializes). To keep it testable without real threads, `events` is a plain generator that also accepts an injected clock/sleep is overkill — instead test `start`+`get` with a fast fn and poll `get` until `done`; test `friendly_stage` separately (A4). Provide `events` but test it by driving a job whose fn returns immediately (loop yields one done frame).

- [ ] Test: `start(lambda: 42)`; poll `get(id)` until `status=="done"`; `result==42`.
- [ ] Test: `start(lambda: 1/0)`; eventually `status=="error"`, `error` set.
- [ ] Test: `events(id)` for a finished job yields a frame containing `"done"`.
- [ ] Implement. Green gate. Commit.

### Task A6: extract route + job → doc data

**Files:** Modify `src/doc2tests/api/app.py`; Create `src/doc2tests/api/deps.py`; Test `tests/api/test_extract.py`

- `deps.py`: `get_store()` singleton `WorkspaceStore`, `get_jobs()` singleton `JobManager`, `get_extract_provider()`/`get_image_provider()` (wrap `orchestrator/config.py`, overridable in tests via app state).
- `POST /api/extract` (multipart `file`): save temp, `store.new(filename)`, start a job that runs `ingest_parse` + `detect_fields` on a `GraphState`, writes results into the workspace, returns `JobRef{job_id, doc_id}`.
- `GET /api/jobs/{id}/events`: `StreamingResponse(media_type="text/event-stream")` from `jobs.events`.
- `GET /api/docs/{doc_id}`: `DocDataDTO`.
- `GET /api/image/page/{doc_id}`: page png.

Test uses a **stub provider** (reuse the vision stub pattern from existing pipeline tests) injected via `app.dependency_overrides`.

- [ ] Test: POST a tiny fixture image with stub provider → job → poll events/`get` → `GET /api/docs/{doc_id}` returns detected + doc_summary.
- [ ] Implement. Green gate. Commit.

### Task A7: generate route

**Files:** Modify `app.py`; Test `tests/api/test_generate.py`

`POST /api/docs/{doc_id}/generate` body `GenerateReq`: map `values` → `list[DetectedValue]` (reuse the id/slug logic from old `_review_phase`), set on workspace `detected`, build `GraphState(detected=..., config=RunConfig(n=n))`, start job running `generate_population`, store `population`, then `repo.save_source(...)` → workspace.source_id. Result payload = `list[VariantDTO]` (+ diagnostics served via `/api/docs/{id}` extension or a `/variants` GET).

- [ ] Test: after extract (stub), POST generate with edited values + n=3 → job done → 3 variants; slot-shared values identical across the two same-slot fields.
- [ ] Implement. Green gate. Commit.

### Task A8: render route (metered)

**Files:** Modify `app.py`; Test `tests/api/test_render.py`

`POST /api/docs/{doc_id}/render` body `RenderReq{variant_index}`: start job running `render_variant(as_document_result, index, image_provider)`; store bytes in `workspace.rendered[index]`; `repo.save_generated(source_id, index, values, img)`. `GET /api/image/generated/{doc_id}/{index}` serves it.

- [ ] Test: with a **stub image provider** (returns fixed PNG bytes), render variant 0 → job done → `GET` returns those bytes; `rendered` marks index 0.
- [ ] Implement. Green gate. Commit.

### Task A9: batch + archive + logs routes

**Files:** Modify `app.py`; Test `tests/api/test_batch.py`, `tests/api/test_archive.py`

- `POST /api/batch` (multipart list + n + workers): job → `process_batch`; result = per-file summaries (register each source). Each file becomes a workspace so its variants can be rendered by the existing render route (map file→doc_id in the batch result).
- `GET /api/sources`, `GET /api/sources/{id}/generated`, `GET /api/image/generated/{id}` (by generated-row id) from `repo`.
- `GET /api/logs?n=400` → `recent_logs(n)`.

- [ ] Test batch: 2 stub files → job done → 2 results, each with population + a doc_id.
- [ ] Test archive: monkeypatch `repo` (SQLite fixture like `tests/db/test_repo.py`) → sources/generated endpoints return rows.
- [ ] Implement. Green gate. Commit.

---

## Phase B — Frontend (React)

### Task B1: Vite scaffold + Tailwind + RTL + theme

**Files:** Create `frontend/` (package.json, vite.config.ts, tsconfig, tailwind.config.ts, postcss, index.html `dir="rtl" lang="he"`, src/main.tsx, src/index.css, src/theme.ts)

- Vite React-TS template; add Tailwind; `index.html` sets RTL + Heebo font (self-host or `@fontsource/heebo` to avoid CDN). Theme: `data-theme` on `<html>` + Tailwind `dark:` via class strategy; persisted to localStorage in a Zustand `useUI` store.
- `vite.config.ts` proxies `/api` → `http://localhost:8501` in dev.

- [ ] `npm install` in `frontend/`. `npm run build` succeeds.
- [ ] Commit.

### Task B2: API client + TanStack Query + SSE hook

**Files:** Create `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`, `frontend/src/api/sse.ts`; Test `frontend/src/api/sse.test.ts`

- `client.ts`: typed `fetch` wrappers for every endpoint (mirrors A2 DTOs in TS types under `src/api/types.ts`).
- `sse.ts`: `useJobEvents(jobId)` → `EventSource('/api/jobs/{id}/events')`, exposes `{stage, elapsed, progress, done, result, error}`; closes on done/error.
- `hooks.ts`: TanStack Query mutations `useExtract`, `useGenerate`, `useRender`, queries `useDoc`, `useSources`, `useGenerated`, `useLogs`.

- [ ] Vitest: `useJobEvents` parses a mocked EventSource message into state (mock `EventSource`).
- [ ] `npm run test` + `npm run build`. Commit.

### Task B3: AppShell (sidebar nav + header + theme toggle)

**Files:** Create `frontend/src/components/AppShell.tsx`, `frontend/src/store/ui.ts`

- Sidebar: יחיד / אצווה / מאגר; header with title + theme toggle (◐). Clean cards, Tailwind, RTL logical spacing.
- [ ] Vitest: renders three nav items; clicking toggles `view` in store; theme toggle flips `data-theme`.
- [ ] Build + test. Commit.

### Task B4: UploadZone + Stepper + LiveStatus

**Files:** Create `UploadZone.tsx`, `Stepper.tsx`, `LiveStatus.tsx`

- `UploadZone`: drag/drop + click, accepts jpg/png/pdf/docx.
- `Stepper`: 5 steps (העלאה/זיהוי/סקירה/יצירה/הורדה), active/done styling.
- `LiveStatus`: consumes `useJobEvents`, shows Hebrew stage + elapsed + optional progress bar.
- [ ] Vitest: `Stepper` marks correct active/done; `LiveStatus` shows stage text from a mocked hook.
- [ ] Build + test. Commit.

### Task B5: ReviewTable

**Files:** Create `ReviewTable.tsx`; Test `ReviewTable.test.tsx`

Editable rows: label, value, `field_type` (select of FieldType values), `is_personal` (checkbox), `slot` (text). Add-row + delete-row. N picker. Emits reviewed values on "צור דאטה".

- [ ] Vitest: edit a value, toggle personal, add a row → onSubmit receives the updated array incl. the new row; type select constrained to FieldType options.
- [ ] Build + test. Commit.

### Task B6: VariantsTable + Gallery + Diagnostics

**Files:** Create `VariantsTable.tsx`, `Gallery.tsx`, `Diagnostics.tsx`

- `VariantsTable`: one row/variant, value columns, "יצירת טופס" checkbox, status (✓/ממתין), buttons render-selected / render-all → calls `useRender` per index (sequential, LiveStatus per job).
- `Gallery`: rendered images grid + per-image download + zip (zip built client-side via `jszip`, or a backend `/api/docs/{id}/zip`). Use backend zip to avoid a client dep → add `GET /api/docs/{doc_id}/zip` in A-phase follow-up.
- `Diagnostics`: per-field end-to-end table (label/type/replace?/slot/original/generated).
- [ ] Vitest: selecting two checkboxes → render-selected calls render with indices [i,j]; Diagnostics renders a row per detected field.
- [ ] Build + test. Commit.

### Task B7: Views wiring (Single, Batch, Archive)

**Files:** Create `views/SingleView.tsx`, `views/BatchView.tsx`, `views/ArchiveView.tsx`, `components/LogsPanel.tsx`, wire in `App.tsx`

- `SingleView`: upload → extract(job/LiveStatus) → ReviewTable → generate(job) → VariantsTable/Gallery/Diagnostics.
- `BatchView`: multi-upload + N + workers → batch job → per-file cards (VariantsTable each).
- `ArchiveView`: sources list → generated variants → image viewer + download + values.
- `LogsPanel`: collapsible, polls `useLogs`.
- [ ] Vitest (light): SingleView renders UploadZone initially; ArchiveView lists sources from mocked query.
- [ ] Build + test. Commit.

---

## Phase C — Docker + cleanup

### Task C1: Multi-stage Dockerfile + compose + `GET /zip`

**Files:** Modify `Dockerfile`, `docker-compose.yml`, `.dockerignore`; add `GET /api/docs/{doc_id}/zip` (uses `zip_images`)

- Stage 1 `node:20`: `COPY frontend/`, `npm ci`, `npm run build` → `/frontend/dist`.
- Stage 2 python: as today + `COPY --from=build /frontend/dist ./frontend/dist`; `create_app()` mounts it. `CMD ["uvicorn","doc2tests.api.app:app","--host","0.0.0.0","--port","8501"]`.
- `.dockerignore`: add `frontend/node_modules`, `frontend/dist`.
- [ ] `uv run pytest -q` for the new `/zip` route (stub images → valid zip bytes).
- [ ] Commit.

### Task C2: Remove Streamlit

**Files:** Delete `src/doc2tests/ui/app.py`, `.streamlit/`; `uv remove streamlit`; keep `ui/helpers.py`. Update `CLAUDE.md` UI/commands section.

- [ ] Grep confirms no remaining `import streamlit`. Green gate. Commit.

### Task C3: End-to-end verify in docker-compose

- [ ] `docker compose up --build`; hit `/api/health`; load the SPA; (with a real key, one manual extract). Report; do NOT auto-run paid image renders.
- [ ] Commit any fixups.

---

## Self-review notes

- Spec coverage: every spec feature maps to a task (single/batch/archive → B7; realtime → A5/B2/B4; logs → A9/B7; persistence → A7/A8; docker → C1; removal → C2).
- Zip: spec mentions zip download → added `GET /api/docs/{doc_id}/zip` in B6/C1.
- Types consistent: DTOs defined in A2 reused as TS types in B2; `friendly_stage` (A4) used by `jobs.events` (A5) and mirrored client-side by SSE payload.
- No paid image calls in any automated test — all image/vision providers are stubbed; real renders only in the manual C3 step.

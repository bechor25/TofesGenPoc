# End-to-end testing guide

Two layers: **automated** (fast, free — run these constantly) and **manual browser**
(real pipeline; the image render costs money, so do it deliberately).

## 0. Automated checks (no cost, run every change)

```bash
# Backend — EXCLUDE the two paid live tests (they hit real OpenAI when a key is set):
uv run pytest -q --ignore=tests/orchestrator/test_live_e2e.py \
                 --ignore=tests/extraction/test_live_openai.py
uv run mypy src
uv run ruff check src tests

# Frontend:
cd frontend && npm run build && npm run test
```

All providers are stubbed in these tests — they exercise the full API flow
(extract → generate → render → archive) without a network call.

## 1. Bring the stack up

```bash
docker compose up --build          # postgres (db) + FastAPI/React app on :8501
```

- App: <http://localhost:8501>
- Postgres: `localhost:5432` (tofes/tofes/tofes)
- `OPENAI_API_KEY` and model overrides come from `.env` (never committed).

Health check (no cost):

```bash
curl -s http://localhost:8501/api/health          # -> {"status":"ok"}
```

## 2. API-only smoke test (real extraction, NO paid image render)

```bash
# start an extraction job
curl -s -F "file=@tests/fixtures/doc2_printed_tax_letter.jpeg" \
     http://localhost:8501/api/extract
# -> {"job_id":"job-1","doc_id":"doc-1"}

# poll the job (extraction on gpt-5.1 can take minutes — this is expected)
curl -s http://localhost:8501/api/jobs/job-1       # status: running -> done

# watch live status as Server-Sent Events (stage + elapsed)
curl -N http://localhost:8501/api/jobs/job-1/events

# see the detected values + doc summary
curl -s http://localhost:8501/api/docs/doc-1

# generate DATA only (cheap) — reuse the detected values you got above
curl -s -X POST http://localhost:8501/api/docs/doc-1/generate \
     -H 'Content-Type: application/json' \
     -d '{"n":3,"values":[{"label":"שם","value":"דנה","field_type":"hebrew_name","is_personal":true,"slot":null}]}'
# poll that job, then GET /api/docs/doc-1 again -> variants[] filled
```

Stop before `/render` if you don't want to spend image credits.

## 3. Full manual test in the browser (includes the PAID render)

1. Open <http://localhost:8501>. The SPA loads (sidebar: **מסמך יחיד / אצווה / מאגר**,
   theme toggle top-left). Confirm RTL + dark/light toggle works.
2. **מסמך יחיד** → drag a form (JPG/PNG/PDF/DOCX) onto the drop zone.
3. Watch the **live status** card — it streams the real stage (מתעתק / מבין ומבנה שדות …)
   and elapsed seconds over SSE. Extraction is slow on gpt-5.1; that is expected.
4. The **review table** appears with the page image + one-line doc understanding. Edit
   labels/values, tick «אישי?» for values to replace, set «קישור» to tie repeated
   values together, pick N, then **צור דאטה (ערכים בלבד)**.
5. The **variants table** shows N validated rows. Tick «יצירת טופס» on one row and press
   **רנדר נבחרים** (or **רנדר הכל**). This is the **expensive gpt-image-2 call** — one per
   variant. The rendered image appears in the gallery; download it or grab the zip.
6. Open **אבחון** to see per-field original→generated; open **לוגים** (bottom) for the
   full end-to-end log.
7. Switch to **מאגר** — the source appears with a unique id and every image generated
   under it; click a source to view/download its variants.

## 4. Tear down

```bash
docker compose down            # keep the archive volume
docker compose down -v         # also wipe the postgres volume (pgdata)
```

## Notes

- **Cost:** data generation is free; every rendered image is a metered gpt-image-2 call.
  Render deliberately, a few variants at a time.
- **State:** the in-memory workspace (doc_id) is lost on app restart; rendered images are
  persisted to Postgres and remain visible under **מאגר**.
- **Dev without Docker:** `uv run uvicorn doc2tests.api:app --port 8501` for the API and
  `cd frontend && npm run dev` for the SPA (Vite proxies `/api` to :8501).

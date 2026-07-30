# doc2tests — Workflow Integration Guide

How to drive the document → test-bank pipeline from an EXTERNAL orchestrator
(multi-agent system, n8n, LangGraph, cron, plain scripts). The whole pipeline is a
**headless HTTP service** — no UI required. Every stage is one HTTP call; the heavy
stages are async jobs you start and then poll (or stream over SSE).

---

## 1. What the service exposes

One FastAPI app (the same one that serves the SPA) on **`:8501`**. Base URL below is
written as `$BASE` (e.g. `http://localhost:8501`, or wherever you deploy it).

The product it produces: from a **source document** it generates **N validated fake-data
variants**, then renders each as an image at a chosen **recognition-difficulty (1-10)**.
Rendered images accumulate under the source as a **test bank**, each tagged with its
difficulty score. That bank is what you feed to the external model under test.

Pipeline stages (all wrapped as HTTP):

```
upload source ──▶ open (extract, cached after 1st time) ──▶ generate data (N)
      ──▶ render variant @ difficulty D  (repeat) ──▶ collect bank (filter by difficulty)
```

---

## 2. Deploy / prerequisites

- Run with `docker compose up --build` (app on `:8501`, Postgres for persistence).
- **`OPENAI_API_KEY`** must be in the app env (`.env`) — extraction (gpt-5.1) and render
  (gpt-image-2) call OpenAI.
- **`DATABASE_URL`** must be set (compose does this) — persistence is REQUIRED for the
  store/bank endpoints (`/api/sources/*`). Without it, upload returns `503`.
- No auth is built in. If you expose it beyond localhost, put it behind your own gateway.

---

## 3. The async-job model (the only pattern you must implement)

Slow stages return a job immediately:

```
POST ...            -> { "job_id": "job-12", "doc_id": "doc-3" }
```

Then EITHER poll:

```
GET $BASE/api/jobs/job-12
  -> { "id":"job-12", "status":"running", "error":null, "result":null }
  -> ... poll every ~2s ...
  -> { "id":"job-12", "status":"done", "error":null, "result": { ... } }
```

`status` is one of `running | done | error`. On `error`, `error` holds the message.

OR stream (Server-Sent Events), if your orchestrator supports it:

```
GET $BASE/api/jobs/job-12/events            (Content-Type: text/event-stream)
  data: {"stage":"מתעתק כל טקסט מהמסמך","elapsed":42,"done":false}
  data: {"stage":"מייצר דאטה מאומת","elapsed":51,"done":false}
  data: {"stage":"","elapsed":63,"done":true,"error":null}
```

Poll for simple orchestrators; SSE for live progress. **Extraction can take minutes**
(gpt-5.1) — set generous timeouts. Extraction is cached after the first run per source,
so later runs are instant.

---

## 4. Endpoint reference (workflow steps)

### Store (sources)
| Step | Call | Returns |
|---|---|---|
| Add document(s) to the store | `POST $BASE/api/sources/upload` (multipart `files`) | `{ "source_ids": [int] }` |
| List sources | `GET $BASE/api/sources` | `[{id, filename, doc_summary, n_generated, has_page_image, has_detected}]` |
| Source thumbnail | `GET $BASE/api/image/source/{id}` | PNG |

Upload de-dupes by the rasterized page image (sha256) — re-uploading the same file
returns the existing `source_id`.

### Run the flow on a source
| Step | Call | Returns |
|---|---|---|
| Open (extract or reuse cache) | `POST $BASE/api/sources/{id}/open` (opt `?force=true` to re-extract) | `{ "doc_id", "job_id"|null, "cached": bool }` |
| Read working state | `GET $BASE/api/docs/{doc_id}` | `{detected[], columns[], variants[], diagnostics[], doc_summary, page_image_url}` |
| Generate N data variants | `POST $BASE/api/docs/{doc_id}/generate` body `{ "values":[...], "n":50 }` | `{ "job_id" }` |
| Render one variant @ difficulty | `POST $BASE/api/docs/{doc_id}/render` body `{ "variant_index":0, "difficulty":3 }` | `{ "job_id" }` |

- If `open` returns `cached:true` (and no `job_id`), the detected values are already
  loaded — skip straight to generate.
- `values` for generate = the `detected` array from `GET /api/docs/{doc_id}` (auto-approve),
  or your own edited list. Each item: `{label, value, field_type, is_personal, slot}`.
- `difficulty` 1-10 is clamped server-side. `1` = clean copy; higher = harder to read.

### Collect the bank (outputs)
| Step | Call | Returns |
|---|---|---|
| List generated (optionally one difficulty) | `GET $BASE/api/sources/{id}/generated?difficulty=3` | `[{id, variant_index, values, difficulty}]` |
| Which difficulties exist | `GET $BASE/api/sources/{id}/difficulties` | `[int]` |
| One image | `GET $BASE/api/image/archived/{generated_id}` | PNG |
| Download all (optionally one difficulty) | `GET $BASE/api/sources/{id}/zip?difficulty=3` | ZIP |

The bank **accumulates**: every render adds a row (never overwrites), so `50 @ diff3`
plus `50 @ diff10` coexist under the same source. `values` on each row = the fake data on
that test image; `difficulty` = its score.

### Misc
| Call | Purpose |
|---|---|
| `GET $BASE/api/health` | liveness → `{"status":"ok"}` |
| `GET $BASE/api/logs?n=400` | recent end-to-end logs |
| `POST $BASE/api/batch` (multipart `files`, `n`, `workers`) | one job that extracts+generates many files |

---

## 5. Recipe: "produce N test images at difficulty D from source S"

The canonical workflow node sequence (auto-approve, no human review):

```
1. source_id  ← POST /api/sources/upload            (or reuse an existing source id)
2. open       ← POST /api/sources/{source_id}/open
                 if open.job_id: poll GET /api/jobs/{open.job_id} until done
   doc_id = open.doc_id
3. doc        ← GET  /api/docs/{doc_id}
4. gen        ← POST /api/docs/{doc_id}/generate  { values: doc.detected, n: N }
                 poll GET /api/jobs/{gen.job_id} until done
5. for i in 0..N-1:
       r ← POST /api/docs/{doc_id}/render  { variant_index: i, difficulty: D }
       poll GET /api/jobs/{r.job_id} until done          # metered: 1 gpt-image-2 call each
6. bank ← GET /api/sources/{source_id}/generated?difficulty=D    # N tagged test images
   zip  ← GET /api/sources/{source_id}/zip?difficulty=D          # or download all at once
```

To build a multi-difficulty bank, repeat step 5-6 with different `D` (data from step 4 is
reused; the bank keeps growing). Renders can run in parallel — each is an independent job.

---

## 6. Mapping to your orchestrator

**Agent tools (multi-agent system).** Register each endpoint as one tool. Minimal set:
`upload_source`, `open_source`, `get_doc`, `generate_data(n)`, `render(variant, difficulty)`,
`await_job(job_id)`, `list_bank(difficulty)`, `download_zip(difficulty)`. The agent plans
"make N tests at difficulty D" by calling them in the order of §5; `await_job` wraps the
poll loop so the rest of the graph stays synchronous.

**n8n.** Each stage = an **HTTP Request** node. Model the job wait as a small loop:
HTTP Request (`GET /api/jobs/{id}`) → **IF** `status == "running"` → **Wait** (2s) → back to
the request; else continue. Use **Split In Batches** over `variant_index` for the render
fan-out. Store `$BASE`, `source_id`, `doc_id`, `job_id` in the workflow's data between nodes.

**LangGraph / custom code.** Wrap the HTTP calls as node functions; the job poll is a
`while status=="running": sleep; get` helper. (Note: this repo already contains the pipeline
as LangGraph nodes in `orchestrator/graph.py` — if your system is in the SAME process you
can import `ingest_parse` / `detect_fields` / `generate_population` / `render_variant`
directly instead of going over HTTP. The HTTP path is for a SEPARATE orchestrator.)

---

## 7. Data-model notes

- **Source id** = the unique document number. Everything generated hangs under it.
- **Dedup**: sources de-dupe by rasterized-page hash; identical re-upload = same source.
- **Accumulation**: renders never overwrite — the bank grows. `variant_index` on a
  generated row is a running counter within the source (not the data-variant index).
- **Difficulty (1-10)** is stored per generated image (its score) AND injected verbatim
  into the gpt-image-2 prompt (see `imagegen/conditions.py`). `1` = clean; `10` = extreme
  real-world capture (angle, dark, flipped, glare, blur…), varied per image.

## 8. Errors, retries, cost

- Any job can end `status:"error"` with a message — surface it; safe to retry the same call.
- HTTP `4xx`: `400` bad file / bad variant index; `404` unknown source/doc/job; `503`
  persistence off (no `DATABASE_URL`).
- **Cost**: `generate` is cheap (data only). **`render` is a metered gpt-image-2 call —
  one per image.** N images = N calls. Drive render deliberately from the workflow.

## 9. Smallest end-to-end (curl)

```bash
BASE=http://localhost:8501
SID=$(curl -s -F "files=@form.pdf" $BASE/api/sources/upload | jq '.source_ids[0]')
OPEN=$(curl -s -X POST $BASE/api/sources/$SID/open); DOC=$(echo "$OPEN" | jq -r .doc_id)
JOB=$(echo "$OPEN" | jq -r '.job_id // empty')
[ -n "$JOB" ] && until [ "$(curl -s $BASE/api/jobs/$JOB | jq -r .status)" != running ]; do sleep 2; done
VALUES=$(curl -s $BASE/api/docs/$DOC | jq '.detected')
GJOB=$(curl -s -X POST $BASE/api/docs/$DOC/generate -H 'Content-Type: application/json' \
        -d "{\"values\":$VALUES,\"n\":50}" | jq -r .job_id)
until [ "$(curl -s $BASE/api/jobs/$GJOB | jq -r .status)" != running ]; do sleep 2; done
# render 50 variants at difficulty 3 (each a metered image call)
for i in $(seq 0 49); do
  RJOB=$(curl -s -X POST $BASE/api/docs/$DOC/render -H 'Content-Type: application/json' \
          -d "{\"variant_index\":$i,\"difficulty\":3}" | jq -r .job_id)
  until [ "$(curl -s $BASE/api/jobs/$RJOB | jq -r .status)" != running ]; do sleep 2; done
done
curl -s "$BASE/api/sources/$SID/zip?difficulty=3" -o bank_difficulty3.zip   # the test bank
```

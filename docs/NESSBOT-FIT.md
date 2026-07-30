# doc2tests × NessBot — Fit Assessment

**Question asked:** Can the NessBot multi-agent / workflow platform host (or drive) the
doc2tests document → test-bank pipeline? If yes, how; if not, what are the gaps to build
around before deciding.

**Verdict:** **Yes — strong fit.** NessBot's workflow engine ("machines") exposes a
superset of the primitives doc2tests currently gets from LangGraph. The pipeline can be
refactored to run *as a NessBot machine* with only additive work on the doc2tests side.
There are **6 gaps**, all of which are either "things doc2tests brings by design" or small
build items — none is a blocker. Details below.

---

## How this was assessed (confidence note)

- The full authenticated catalog `GET /api/v1/api-catalog` returns **`401 Not
  authenticated`** without a token, so exact request/response **schemas were not read**.
- What *was* read: the built admin SPA bundle. From it I harvested **94 unique
  `/api/v1/**` endpoints** (the platform's real API surface) and the **machine node-kind
  string literals** used by its workflow editor. That is enough for a path-level verdict
  and to name the gaps, but the items marked **⚠ verify** below need the authed catalog to
  confirm exact shapes.
- To upgrade this from path-level to schema-level: paste a bearer token (or let me `POST
  /api/v1/auth/login`) and I'll pull the real catalog and tighten every ⚠ item.

---

## 1. What NessBot is (relevant surface)

A full agent + workflow platform. Groups seen in the API:

| Group | Endpoints (sample) | Relevance to us |
|---|---|---|
| **Machines** (WF engine) | `/machines`, `/machines/runs`, `/machines/events/stream`, `/machines/signals`, `/machines/approvals`, `/machines/checkpoints`(+`/restore`), `/machines/execute/legacy-workflow`(+`/stream`), `/machines/ops/*` | **The orchestrator.** Start/list runs, stream events, human approvals, durable checkpoints, budget-stopped runs. |
| **Workflows** (authoring) | `/workflows`, `/workflows/compile-preview`, `/workflows/import`, `/workflows/lint` | Author/import/validate a machine definition. |
| **Agents / tools** | `/agents`(+`/export-bundle`), `/agent/run`, `/agent/info`, `/agent/servers`, `/tools`, `/skills`, `/mcp/servers`, `/magic-keywords` | Agent runtime + **tool & MCP-server registry** → doc2tests can plug in as tools. |
| **Models** | `/models/invoke`, `/models/providers`(+`/fetch-models`), `/tiers`, `/pricing`, `/quotas`, `/admin/settings/run-budget` | Central model gateway + **cost/budget controls**. |
| **RAG** | `/rag`, `/rag/collections`, `/rag/ingest`, `/rag/search`, `/rag/embedding-models` | Not required by our flow (optional: index source docs). |
| **Exports / artifacts** | `/exports/render`, `/exports/render-zip`, `/exports/preview`, `/exports/artifacts`, `/export-formats`, `/artifacts/search` | Artifact store + zip export → could host the test bank. **⚠ `exports/render` is template/doc export, NOT vision image-edit** (see gaps). |
| **Copilot** | `/copilot-sessions/*` (`from-workflow`, `llm-node-assist`, `agent-prefs-assist`, `stream`) | AI-assisted workflow building. Nice-to-have. |
| **Infra / auth** | `/auth/*`, `/credentials`, `/vault`(node), `/plugins`(+`/install`), `/chat/attachments/inflate`, `/admin/settings/file-upload`, `/voice` | Secrets, credentials, file upload, plugins. |

### Machine node kinds (from the editor bundle)

`start`, `entry`, `endpoint`, `event`, `steps`, `parallel`, `iteration`, `iteration_lt`,
`submachine`, `signal_present`, `approval` / `human_approval` / `interrupt`, `fail_branch`,
`score`, `test_data`, `default_value`, `variable_lt`, plus integration kinds `kafka`,
`redis`, `storage`, `vault`, `blob`, `image`, `doc`.

That set is what makes this a fit — see the mapping.

---

## 2. Capability mapping — doc2tests need → NessBot feature

| doc2tests pipeline need | NessBot primitive | Fit |
|---|---|---|
| Orchestrate stages in order | `machines` graph (`start`→`steps`→…) | ✅ native |
| Call a stage that lives in our service | **`endpoint`** node (external HTTP) — our REST API | ✅ our API already exists |
| Long extraction/render as async job | start-job + **`iteration_lt`** poll loop + `event`/`signal_present`; **`checkpoints`** for durability | ✅ buildable **⚠ verify** `endpoint` timeout / poll pattern |
| **Human review gate** (approve/edit detected values) | **`approval` / `human_approval` / `interrupt`** + `/machines/approvals` | ✅ direct match (replaces LangGraph `interrupt_before`) |
| Inject approved values back into the run | **`/machines/signals`** + `signal_present` | ✅ native |
| **Render N variants** (fan-out) | **`iteration` / `iteration_lt`** (loop over N) or **`parallel`** | ✅ native |
| Pass the page image / rendered PNG between nodes | **`blob` / `image` / `storage`** kinds | ✅ present **⚠ verify** ref-passing shape |
| Reusable "make test bank" unit inside a bigger flow | **`submachine`** | ✅ native |
| Live progress to a UI / caller | **`/machines/events/stream`** (SSE) | ✅ matches our job SSE |
| Hold `OPENAI_API_KEY` / service creds | **`vault`** node + `/credentials` | ✅ native |
| Cap spend on metered image gen | `/admin/settings/run-budget` + `/machines/ops/budget-stopped-runs` | ✅ **⚠ scope** — see gap 3 |
| Collect + zip the bank | `/exports/render-zip`, `/exports/artifacts`, `/artifacts/search` | ✅ optional target (or keep our `/sources/{id}/zip`) |

**Bottom line:** every stage and control-flow need in our pipeline has a native NessBot
node. The engine is a superset of our current LangGraph.

---

## 3. What doc2tests *brings* (not in NessBot — by design, not gaps)

These are our domain value; NessBot has no equivalent and shouldn't. They stay as
doc2tests tools/endpoints that a machine calls:

- **Grounded extraction** — two-pass gpt-5.1 vision (transcribe + understand: personal?,
  type, slot). NessBot's `/models/invoke` is generic; it has no form-understanding.
- **gpt-image-2 form-edit** — edit the *original* form image in place, replacing only
  personal values, difficulty photo-conditions injected. **NessBot `exports/render` is
  document/template rendering, not vision image-edit** — see gap 1.
- **Israeli validators** (id checksum, dates, phone…) + slot coherence.
- **Source store**: dedup-by-page-hash, per-source extraction cache, difficulty-tagged
  accumulating test bank.

→ Expose these as either (A) HTTP endpoints (already done) or (B) an **MCP server**
registered via `/mcp/servers`. Both work; see §5.

---

## 4. Gaps (decision-relevant)

| # | Gap | Impact | To close |
|---|---|---|---|
| 1 | **Image-edit is ours, not NessBot's.** `exports/render` renders docs/templates, not a vision edit of a photographed form. | Can't "replace" our render with a NessBot node. Not a blocker — it's the value we bring. | Keep render as a doc2tests `endpoint`/MCP tool. **⚠ verify** exactly what `exports/render` does with the authed spec. |
| 2 | **Long-running async await.** Extract (gpt-5.1) + render (gpt-image-2) take minutes; an `endpoint` node needs to await long or poll. | Determines machine shape (single long call vs start+poll loop). | Confirm `endpoint` node timeout & whether it supports a start→`iteration_lt` poll pattern (engine clearly can — `event`/`signal_present`/`checkpoints` exist). **⚠ verify** schema. |
| 3 | **Budget cap scope.** `run-budget` almost certainly meters spend routed through `/models/invoke`. Our gpt-image-2 cost happens **inside doc2tests**, invisible to NessBot's meter. | NessBot's budget guard may **not** auto-cap our image spend. | Either (a) enforce the N-render cap on the doc2tests side (already metered, on-demand), or (b) report cost back / route image calls through NessBot. Decide per how much you trust the machine author. |
| 4 | **Binary passing between nodes.** `blob`/`image`/`storage` kinds exist but the exact "endpoint returns PNG → stash → pass ref downstream" shape is unread. | Affects whether images flow through the machine or stay addressed by our IDs/URLs. | Simplest: machine passes **our** `generated_id`/URLs, not bytes. **⚠ verify** if you want bytes in-graph. |
| 5 | **doc2tests has no auth.** If NessBot reaches it over the network, the endpoint is open. | Security if exposed beyond localhost. | Add a bearer/API-key check to doc2tests; store the key in NessBot `vault`/`credentials`. Small build item. |
| 6 | **Bank lives in our DB, not NessBot artifacts.** Source dedup + difficulty bank are doc2tests-native. | If you want the bank visible as NessBot artifacts/exports, that's extra. | Optional: after each render, `POST /exports/artifacts` (or let the machine collect refs). Otherwise keep `/sources/{id}/zip`. |

None of 1–6 blocks integration. 1/6 are "by design"; 2/3/4 are **⚠ verify** (need the
authed catalog); 5 is a small, known build item.

---

## 5. Recommended path

Two styles, not exclusive:

**A. HTTP `endpoint` nodes (fast path — works today).**
Author one NessBot **machine** = doc2tests test-bank flow. Nodes:

```
start
 → endpoint  POST /api/sources/upload            (or reuse source_id)
 → endpoint  POST /api/sources/{id}/open  ─┐
 → iteration_lt  poll GET /api/jobs/{id}   │  (until status != running)
 → endpoint  GET  /api/docs/{doc_id}       ┘
 → approval   human confirms/edits detected values      ← maps to our review gate
 → endpoint  POST /api/docs/{doc_id}/generate {values, n:N}
 → iteration_lt  poll job
 → iteration (i=0..N-1) / parallel:
        endpoint POST /api/docs/{doc_id}/render {variant_index:i, difficulty:D}
        iteration_lt poll job                            ← metered: 1 image each
 → endpoint  GET /api/sources/{id}/zip?difficulty=D      → artifact
```

Minimal doc2tests change (just gap 5: add auth). NessBot owns orchestration, approvals,
checkpoints, budget-stopped-runs. This is exactly what `docs/INTEGRATION.md` specifies,
now mapped to concrete node kinds.

**B. MCP server (more native to the agent model).**
Wrap the four stage functions (`ingest_parse`, `detect_fields`, `generate_population`,
`render_variant`) as MCP tools, register via `POST /api/v1/mcp/servers`. Agents/machines
then call `open_source`, `generate_data(n)`, `render(variant, difficulty)`,
`list_bank(difficulty)` as tools — good if you want an agent to *plan* "make N tests at
difficulty D" rather than a fixed machine. Reuses the same doc2tests internals.

**Recommendation:** ship **A** first (zero pipeline rewrite, immediate), add **B** if you
want agent-driven planning. Keep the gpt-image-2 render and the source/bank store on the
doc2tests side in both cases (§3).

---

## 6. Next step to make this decision-grade

Give me a token for `nessbot.localhost` (or creds for `POST /api/v1/auth/login`) and I'll
read `GET /api/v1/api-catalog` to confirm the four **⚠ verify** items (endpoint-node
timeout/poll, binary/artifact passing, `exports/render` semantics, budget scope) and turn
§5-A into an importable machine spec via `/api/v1/workflows/import`.

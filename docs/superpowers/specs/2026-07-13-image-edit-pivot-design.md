# Design: Image-Edit Pivot — Form Value Replacement via gpt-image-2

**Date:** 2026-07-13
**Status:** Approved (pending user spec review)
**Supersedes:** the HTML-template-recreation approach (`2026-07-08-doc2tests-design.md`).

## 1. Problem & Goal

Take any Israeli form (photo / PDF / Word — medical, ביטוח לאומי, etc.),
detect every personal value in it, and produce **N copies of the same image with the
personal values replaced by newly generated, VALIDATED values** — pixel-faithful to the
original design. The user reviews detected values, adds any that were missed, picks N,
and downloads N result images.

The previous approach recreated the document as HTML and filled it. The user rejected
that (structural, never pixel-faithful). This pivot edits the **original image directly**
with an image-editing model, so the output is the real form with only the values changed.

## 2. Key Decision: Model

- Engine: **`gpt-image-2`** (verified available on the account, released 2026-04-21)
  via `client.images.edit(...)`.
- `input_fidelity="high"` — preserves the input image faithfully, changing only what the
  prompt asks. This is what makes "same form, only values swapped" viable.
- SDK: `openai==2.44.0` (installed); `images.edit` supports `image`, `prompt`,
  `input_fidelity`, `mask`, `model`, `n`, `size`, `quality` — all verified.
- Hebrew fidelity: gpt-image-2 is materially better than gpt-image-1 at text rendering +
  layout preservation. Output quality is evaluated visually by the user; masking (below)
  is the fallback if drift appears.
- **Masking is a future enhancement, not v1.** v1 is prompt-only with `input_fidelity=high`.
  Detected value bboxes are retained so a mask can be added later if needed.

## 3. Data Decision

Generated data is **valid-only** (no negative/boundary QA classes). Every one of the N
variants is a realistic, fully-valid "person": Israeli ID with correct checksum, coherent
dates, valid phone, etc. The test-class machinery (equivalence/boundary/negative,
relation-violation, coverage report) is removed.

## 4. Flow (6 stages)

```
1. ingest        form (image/pdf/word) → page image(s) (PNG bytes)
2. detect        vision model reads the image → list of DetectedValue
                 {label, value, value_kind, field_type, is_personal, bbox?}
3. review gate   UI: show detected values; user confirms / edits / adds missed values,
                 marks which are personal (replaceable), enters N
4. generate      N Records, each {field_id → new valid value}, validated (retry-until-valid)
5. edit          per variant: gpt-image-2 images.edit(original, prompt(old→new map),
                 input_fidelity=high) → edited PNG
6. download      N result images (individual + zip)
```

One human-in-the-loop interrupt at stage 3 (LangGraph `interrupt_before`).

## 5. Architecture

### Keep & adapt
- `providers/base.py`, `providers/openai_provider.py` — add `edit_image(image_bytes, prompt,
  *, mask=None, size, quality) -> bytes` to the protocol + OpenAI impl (calls `images.edit`,
  model `gpt-image-2`, `input_fidelity="high"`, returns decoded PNG bytes).
- `providers/factory.py`, `providers/ollama_provider.py` — Ollama keeps text/vision only;
  `edit_image` raises `NotImplementedError` (image edit is OpenAI-only for now).
- `ingest/loaders.py` — `detect_kind` + `load_images`. Extend to rasterize every kind to a
  page image (see `ingest/rasterize.py`).
- `ingest/parse.py` — vision value detection. Prompt already exhaustive; output feeds
  DetectedValue. Keep raw_text + fields.
- `deid/detect.py`, `deid/classify.py` — classify each detected value → field type + whether
  personal (drives which values get replaced).
- `generate/population.py` — simplify to valid-only: N records, each field a valid value for
  its type (retry-until-`validate()`-passes). Drop `_class_counts`, negatives, violations.
- `generate/strategies.py` — keep only valid-value generation per type. Drop `.negative()`
  / `.boundary()` usage.
- `generate/relations.py` — keep valid ordering (e.g. date A ≤ date B); drop `violate_order`.
- `validators/*` — unchanged (single source of truth for "valid").
- `orchestrator/graph.py` — simplify nodes to: ingest → detect → **review_gate (interrupt)**
  → generate → edit_images → END. MemorySaver checkpointer retained.
- `orchestrator/config.py` — build OpenAI provider from env (unchanged).
- `ui/app.py` — rewritten for the new flow (see §6).
- `common/logging.py`, `common/json_utils.py`, `common/slug.py` — unchanged.
- `contracts/` — slim down (see §7).

### New
- `ingest/rasterize.py` — one image per input kind (image, pdf, word — ALL first-class):
  - image → passthrough (PNG/JPEG bytes)
  - pdf → PyMuPDF render each page → PNG (already available)
  - docx/word → LibreOffice `soffice --headless --convert-to pdf` → PyMuPDF → PNG.
    `soffice` is verified installed (`/opt/homebrew/bin/soffice`). If absent at runtime,
    raise a clear StageError naming the missing tool. Path is resolved via `shutil.which`
    (fallback `/Applications/LibreOffice.app/Contents/MacOS/soffice`).
  Input kinds are image, pdf, word — nothing else. (HTML is out of scope.)
- `imagegen/edit.py` — `edit_form_image(original_png, replacements, provider, doc_hint) -> png`
  builds the strong prompt (§8) from the old→new replacement map and calls `provider.edit_image`.
- `imagegen/__init__.py`.

### Delete (rejected approaches + now-dead code)
- `render/{layout,html,style,docx,docxutil,canonical,overlay,run}.py`
- `template/{anchor,build}.py`
- `schema/infer.py` (+ `schema/`)
- `ingest/ocr_boxes.py` (label-anchoring no longer used; masking, if added, uses vision bboxes)
- `coverage/report.py` (+ `coverage/`)
- `api/main.py` — the FastAPI surface; the Streamlit UI is the single entry point. (Remove
  `api/` unless we still want a REST surface — default: remove for YAGNI.)
- All corresponding tests under `tests/render/`, `tests/template/`, `tests/schema/`,
  `tests/coverage/`, `tests/ingest/test_ocr_boxes*` (none), `tests/api/` (none present).

## 6. UI (Streamlit, RTL)

Pipeline stepper: **העלאה → זיהוי ערכים → סקירה ואישור → יצירה ומילוי → הורדה**.
1. Upload form (image/pdf/html/word) + show the rasterized preview.
2. Detected-values table (editable): label | value | field type | personal? (checkbox).
   User can edit a value, add a missing row, or untick a value that shouldn't be replaced.
3. Number input N (default 10) → "צור".
4. Progress per variant (edit calls run sequentially, logged).
5. Result gallery: N images, each with a download button + "הורד הכל (zip)".
6. Logs expander (existing `recent_logs`).

## 7. Contracts (slimmed)

- `DetectedValue` (new/renamed): `label, value, value_kind, field_type, is_personal, bbox?`.
- `Record`: `index, values: dict[field_id → Value]` (drop `test_class`, `expected_valid`,
  `violates`).
- `Value`: `field_id, value, valid: bool`.
- `GraphState`: `input_ref, config(n, seed), page_images, detected, review, population,
  output_images: list[bytes], errors`.
- Remove: `CanonicalTemplate`, `BBox`-heavy template model (keep a small bbox on
  DetectedValue), `Relation`/`TestClass` coverage fields, `RenderStrategy`, `CoverageReport`.

## 8. Image-Edit Prompt (v1)

System-style instruction embedded in the `prompt` (images.edit has no separate system role):

> You are a precise document-image editor for official Israeli forms (medical / National
> Insurance / bank / tax). You receive one scanned or photographed form. Reproduce it
> **exactly** — identical layout, fonts, colors, stamps, table lines, and handwriting
> style — changing **only** the personal values listed below. For each pair, find the OLD
> value in the image and replace it with the NEW value, matching the original script
> (Hebrew, right-to-left), the same printed-vs-handwritten style, size, and position. Do
> **not** alter any label, static text, logo, or any value not listed. Keep everything else
> pixel-identical. Output the full edited form.
>
> Replacements:
> - "<old>" → "<new>"  (× per personal field)

`input_fidelity="high"`, `size` matched to the source aspect, `quality="high"`.

## 9. Testing (TDD)

- `validators/*` tests — unchanged, still the validity contract.
- `generate/population` — new tests: exactly N records; every value passes `validate()`;
  deterministic by seed; date relations hold.
- `ingest/rasterize` — image passthrough returns PNG; pdf renders ≥1 page; word path renders
  via soffice (skipped only if soffice missing at test time); unknown kind → StageError.
- `imagegen/edit` — prompt builder includes every replacement pair and the fidelity clause
  (pure-string test, no network). Provider `edit_image` mocked.
- `providers/openai_provider` — `edit_image` calls `images.edit` with `model="gpt-image-2"`,
  `input_fidelity="high"` (mock the client; assert kwargs).
- Live tests (skipped without `OPENAI_API_KEY`): one real `edit_image` round-trip on a
  fixture form; assert non-empty PNG returned.
- Whole-graph offline test with a stub provider (deterministic edited-bytes).

## 10. Non-goals / honest limits

- Not pixel-perfect-guaranteed: fidelity depends on gpt-image-2; user evaluates visually.
  Masking is the escalation path if drift appears.
- word rasterization needs LibreOffice (`soffice`) — verified installed on this machine.
- Name-level PII: detection drives replacement; anything the detector misses the user adds
  manually in the review gate (that gate is the completeness backstop).
- Cost/time: N edit calls per run (~N × a few seconds + per-image cost). Sequential, logged.

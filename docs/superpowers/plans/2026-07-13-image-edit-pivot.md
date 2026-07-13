# Image-Edit Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the HTML-recreation pipeline with an image-edit pipeline: ingest any form (image/pdf/word) → rasterize to a page image → detect personal values → user reviews/adds values + picks N → generate N validated variants → gpt-image-2 edits the original image in place → download N faithful images.

**Architecture:** Additive first (new leaf modules: provider `edit_image`, `imagegen/edit.py`, `ingest/rasterize.py`), then one coherent "core pivot" that rewrites contracts + detect + generate + graph and deletes the rejected subsystems, then the Streamlit UI rewrite, then dependency/config cleanup. LangGraph keeps one human interrupt before the review gate. Data is valid-only (no QA negative/boundary classes).

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph, OpenAI SDK 2.44 (`images.edit`, model `gpt-image-2`, `input_fidelity="high"`), PyMuPDF, Pillow, LibreOffice (`soffice`) for word→pdf, Streamlit, Faker, pytest/ruff/mypy(strict).

**Spec:** `docs/superpowers/specs/2026-07-13-image-edit-pivot-design.md`

---

## File Structure

**New:**
- `src/doc2tests/providers/base.py` — add `edit_image` to protocol (modify)
- `src/doc2tests/providers/openai_provider.py` — add `edit_image` (modify)
- `src/doc2tests/providers/ollama_provider.py` — add `edit_image` raising NotImplementedError (modify)
- `src/doc2tests/imagegen/__init__.py`, `src/doc2tests/imagegen/edit.py` — prompt builder + edit call
- `src/doc2tests/ingest/rasterize.py` — any input kind → page image bytes

**Rewritten:**
- `src/doc2tests/contracts/enums.py`, `records.py`, `state.py`, `template.py`
- `src/doc2tests/ingest/parse.py`, `ingest/loaders.py`
- `src/doc2tests/deid/detect.py`
- `src/doc2tests/generate/strategies.py`, `generate/population.py`
- `src/doc2tests/orchestrator/graph.py`, `orchestrator/config.py`
- `src/doc2tests/ui/app.py`

**Deleted:**
- `src/doc2tests/render/` (layout, html, style, docx, docxutil, canonical, overlay, run)
- `src/doc2tests/template/` (anchor, build)
- `src/doc2tests/schema/` (infer)
- `src/doc2tests/coverage/` (report)
- `src/doc2tests/api/` (main)
- `src/doc2tests/ingest/ocr_boxes.py`
- `src/doc2tests/generate/relations.py`
- Matching tests: `tests/render/`, `tests/template/`, `tests/schema/`, `tests/coverage/`, `tests/generate/test_relations.py`, `tests/api/` (none present)

---

## Task 1: Provider `edit_image`

**Files:**
- Modify: `src/doc2tests/providers/base.py`
- Modify: `src/doc2tests/providers/openai_provider.py`
- Modify: `src/doc2tests/providers/ollama_provider.py`
- Test: `tests/providers/test_openai_provider.py`, `tests/providers/test_ollama_provider.py`

- [ ] **Step 1: Write the failing test (OpenAI edit_image)**

Add to `tests/providers/test_openai_provider.py`:

```python
def test_edit_image_calls_images_edit_with_gpt_image_2():
    import base64
    from unittest.mock import MagicMock
    png = b"\x89PNG\r\n\x1a\nORIGINAL"
    returned = base64.b64encode(b"EDITED").decode("ascii")

    client = MagicMock()
    client.images.edit.return_value = MagicMock(data=[MagicMock(b64_json=returned)])

    from doc2tests.providers.openai_provider import OpenAIProvider
    prov = OpenAIProvider(model="gpt-4o", client=client)
    out = prov.edit_image(png, "replace values")

    assert out == b"EDITED"
    kwargs = client.images.edit.call_args.kwargs
    assert kwargs["model"] == "gpt-image-2"
    assert kwargs["input_fidelity"] == "high"
    assert kwargs["prompt"] == "replace values"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/providers/test_openai_provider.py::test_edit_image_calls_images_edit_with_gpt_image_2 -v`
Expected: FAIL — `OpenAIProvider` has no attribute `edit_image`.

- [ ] **Step 3: Add `edit_image` to the protocol**

In `src/doc2tests/providers/base.py`, add to the `LLMProvider` Protocol (after `extract_vision`):

```python
    def edit_image(
        self, image: bytes, prompt: str, *,
        mask: bytes | None = None, size: str = "auto", quality: str = "high",
    ) -> bytes: ...
```

- [ ] **Step 4: Implement `edit_image` on OpenAIProvider**

In `src/doc2tests/providers/openai_provider.py`, add `import io` at top and this method:

```python
    _IMAGE_MODEL = "gpt-image-2"

    def edit_image(
        self, image: bytes, prompt: str, *,
        mask: bytes | None = None, size: str = "auto", quality: str = "high",
    ) -> bytes:
        # gpt-image-2 + input_fidelity=high: preserve the source, change only what
        # the prompt names. images.edit needs a named file-like for the image.
        buf = io.BytesIO(image)
        buf.name = "form.png"
        kwargs: dict[str, Any] = {
            "model": self._IMAGE_MODEL, "image": buf, "prompt": prompt,
            "input_fidelity": "high", "size": size, "quality": quality,
        }
        if mask is not None:
            mbuf = io.BytesIO(mask)
            mbuf.name = "mask.png"
            kwargs["mask"] = mbuf
        resp = self._client.images.edit(**kwargs)
        return base64.b64decode(resp.data[0].b64_json)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/providers/test_openai_provider.py::test_edit_image_calls_images_edit_with_gpt_image_2 -v`
Expected: PASS

- [ ] **Step 6: Write the failing test (Ollama edit_image)**

Add to `tests/providers/test_ollama_provider.py`:

```python
def test_edit_image_not_supported():
    import pytest
    from doc2tests.providers.ollama_provider import OllamaProvider
    prov = OllamaProvider(model="llama3.2-vision")
    with pytest.raises(NotImplementedError):
        prov.edit_image(b"png", "prompt")
```

- [ ] **Step 7: Implement on OllamaProvider**

In `src/doc2tests/providers/ollama_provider.py`, add:

```python
    def edit_image(
        self, image: bytes, prompt: str, *,
        mask: bytes | None = None, size: str = "auto", quality: str = "high",
    ) -> bytes:
        raise NotImplementedError("image editing is OpenAI-only (gpt-image-2)")
```

- [ ] **Step 8: Run both provider test files**

Run: `uv run pytest tests/providers/ -v`
Expected: PASS (all)

- [ ] **Step 9: Commit**

```bash
git add src/doc2tests/providers tests/providers
git commit -m "feat(providers): add edit_image (gpt-image-2, input_fidelity=high)"
```

---

## Task 2: `imagegen/edit.py` — prompt builder + edit call

**Files:**
- Create: `src/doc2tests/imagegen/__init__.py`
- Create: `src/doc2tests/imagegen/edit.py`
- Test: `tests/imagegen/__init__.py`, `tests/imagegen/test_edit.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/imagegen/__init__.py` (empty) and `tests/imagegen/test_edit.py`:

```python
from unittest.mock import MagicMock

from doc2tests.imagegen.edit import Replacement, build_edit_prompt, edit_form_image


def test_prompt_lists_every_replacement_and_fidelity_clause():
    reps = [Replacement(old="123456782", new="204685624"),
            Replacement(old="דנה כהן", new="יוסי לוי")]
    prompt = build_edit_prompt(reps, doc_hint="ביטוח לאומי")
    assert "123456782" in prompt and "204685624" in prompt
    assert "דנה כהן" in prompt and "יוסי לוי" in prompt
    assert "ביטוח לאומי" in prompt
    # fidelity intent is explicit
    assert "only" in prompt.lower()


def test_prompt_skips_empty_or_unchanged():
    reps = [Replacement(old="", new="x"), Replacement(old="a", new="a")]
    prompt = build_edit_prompt(reps)
    # no replacement line rendered for empty-old or old==new
    assert "→" not in prompt


def test_edit_form_image_calls_provider_edit():
    prov = MagicMock()
    prov.edit_image.return_value = b"EDITED"
    reps = [Replacement(old="123456782", new="204685624")]
    out = edit_form_image(b"ORIGINAL", reps, prov, doc_hint="form")
    assert out == b"EDITED"
    args = prov.edit_image.call_args
    assert args.args[0] == b"ORIGINAL"
    assert "204685624" in args.args[1]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/imagegen/test_edit.py -v`
Expected: FAIL — module `doc2tests.imagegen.edit` does not exist.

- [ ] **Step 3: Implement `imagegen/edit.py`**

Create `src/doc2tests/imagegen/__init__.py` (empty) and `src/doc2tests/imagegen/edit.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from doc2tests.common.logging import get_logger
from doc2tests.providers.base import LLMProvider

_log = get_logger("imagegen")

_INSTRUCTION = (
    "You are a precise document-image editor for official Israeli forms "
    "(medical, National Insurance / ביטוח לאומי, bank, tax). You receive one "
    "scanned or photographed form. Reproduce it EXACTLY — identical layout, fonts, "
    "colors, stamps, table lines, and handwriting style — changing ONLY the personal "
    "values listed below. For each pair, find the OLD value in the image and replace it "
    "with the NEW value, matching the original script (Hebrew, right-to-left), the same "
    "printed-vs-handwritten style, size, and position. Do NOT alter any label, static "
    "text, logo, or any value not listed. Keep everything else pixel-identical. Output "
    "the full edited form."
)


@dataclass(frozen=True)
class Replacement:
    old: str
    new: str


def build_edit_prompt(replacements: list[Replacement], doc_hint: str = "") -> str:
    lines = [_INSTRUCTION]
    if doc_hint:
        lines.append(f"Document type hint: {doc_hint}.")
    pairs = [r for r in replacements if r.old.strip() and r.old != r.new]
    if pairs:
        lines.append("Replacements (OLD → NEW):")
        lines += [f'- "{r.old}" → "{r.new}"' for r in pairs]
    return "\n".join(lines)


def edit_form_image(
    original_png: bytes, replacements: list[Replacement], provider: LLMProvider,
    doc_hint: str = "",
) -> bytes:
    prompt = build_edit_prompt(replacements, doc_hint)
    n = sum(1 for r in replacements if r.old.strip() and r.old != r.new)
    _log.info("editing image: %d value replacement(s)", n)
    return provider.edit_image(original_png, prompt)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/imagegen/test_edit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/doc2tests/imagegen tests/imagegen
git commit -m "feat(imagegen): edit prompt builder + edit_form_image"
```

---

## Task 3: `ingest/rasterize.py` — any input → page image

**Files:**
- Create: `src/doc2tests/ingest/rasterize.py`
- Test: `tests/ingest/test_rasterize.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/ingest/test_rasterize.py`:

```python
import shutil
from pathlib import Path

import pytest

from doc2tests.ingest.rasterize import rasterize, soffice_path

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _first_image_fixture() -> Path:
    for p in FIXTURES.iterdir():
        if p.suffix.lower() in {".jpeg", ".jpg", ".png"}:
            return p
    raise AssertionError("no image fixture")


def test_image_passthrough_returns_png_bytes():
    src = _first_image_fixture()
    pages = rasterize(str(src))
    assert len(pages) >= 1
    assert pages[0][:4] == b"\x89PNG"  # normalized to PNG


def test_unknown_kind_raises():
    with pytest.raises(ValueError):
        rasterize("form.txt")


@pytest.mark.skipif(soffice_path() is None, reason="LibreOffice not installed")
def test_docx_renders_at_least_one_page(tmp_path):
    from docx import Document
    docx_path = tmp_path / "f.docx"
    d = Document()
    d.add_paragraph("שם: דנה כהן")
    d.add_paragraph("ת.ז: 123456782")
    d.save(docx_path)
    pages = rasterize(str(docx_path))
    assert len(pages) >= 1
    assert pages[0][:4] == b"\x89PNG"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/ingest/test_rasterize.py -v`
Expected: FAIL — module `doc2tests.ingest.rasterize` does not exist.

- [ ] **Step 3: Implement `ingest/rasterize.py`**

Create `src/doc2tests/ingest/rasterize.py`:

```python
"""Turn any supported input (image / pdf / word) into page images (PNG bytes).
This is the single entry the image-edit pipeline needs: the model edits an image,
so every input kind is normalized to a page image first."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from doc2tests.common.logging import get_logger
from doc2tests.ingest.loaders import detect_kind

_log = get_logger("rasterize")
_MAX_PAGES = 3
_SOFFICE_FALLBACK = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def soffice_path() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    return _SOFFICE_FALLBACK if Path(_SOFFICE_FALLBACK).exists() else None


def _to_png(data: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _pdf_to_png(path: str, dpi: int = 200) -> list[bytes]:
    import fitz  # PyMuPDF

    pages: list[bytes] = []
    with fitz.open(path) as doc:
        for page in doc[:_MAX_PAGES]:
            pages.append(page.get_pixmap(dpi=dpi).tobytes("png"))
    return pages


def _docx_to_pdf(path: str, out_dir: str) -> str:
    soffice = soffice_path()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice (soffice) not found — install it to accept Word documents, "
            "or supply a PDF/image instead."
        )
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, path],
        check=True, capture_output=True, timeout=120,
    )
    pdf = Path(out_dir) / (Path(path).stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError(f"soffice did not produce a PDF for {path}")
    return str(pdf)


def rasterize(path: str) -> list[bytes]:
    """Return page images (PNG bytes) for image, pdf, or word input."""
    kind = detect_kind(path)
    if kind == "image":
        return [_to_png(Path(path).read_bytes())]
    if kind == "pdf":
        return _pdf_to_png(path)
    if kind == "docx":
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _docx_to_pdf(path, tmp)
            pages = _pdf_to_png(pdf)
        _log.info("rasterized word -> %d page image(s)", len(pages))
        return pages
    raise ValueError(f"unsupported kind: {kind}")
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/ingest/test_rasterize.py -v`
Expected: PASS (docx test runs since soffice is installed; passthrough + unknown pass).

- [ ] **Step 5: Commit**

```bash
git add src/doc2tests/ingest/rasterize.py tests/ingest/test_rasterize.py
git commit -m "feat(ingest): rasterize image/pdf/word to page PNGs (word via LibreOffice)"
```

---

## Task 4: Core pivot — contracts, detect, generate, graph (+ delete rejected subsystems)

This task changes the connected core together. Write the new tests first, implement, delete the dead modules and their tests, then run the full suite green.

**Files:**
- Modify: `src/doc2tests/contracts/enums.py`, `contracts/records.py`, `contracts/state.py`, `contracts/template.py`
- Modify: `src/doc2tests/ingest/parse.py`, `ingest/loaders.py`
- Modify: `src/doc2tests/deid/detect.py`
- Modify: `src/doc2tests/generate/strategies.py`, `generate/population.py`
- Modify: `src/doc2tests/orchestrator/graph.py`, `orchestrator/config.py`
- Delete: `render/`, `template/`, `schema/`, `coverage/`, `api/`, `ingest/ocr_boxes.py`, `generate/relations.py`
- Delete tests: `tests/render/`, `tests/template/`, `tests/schema/`, `tests/coverage/`, `tests/generate/test_relations.py`
- Test: `tests/generate/test_population.py`, `tests/generate/test_strategies.py`, `tests/deid/test_detect.py`, `tests/ingest/test_parse.py`, `tests/orchestrator/test_graph.py` (rewrite), `tests/contracts/test_state.py`, `tests/contracts/test_enums.py` (rewrite)

### 4a. Contracts

- [ ] **Step 1: Rewrite `contracts/enums.py`**

```python
from enum import StrEnum


class FieldType(StrEnum):
    hebrew_name = "hebrew_name"
    israeli_id = "israeli_id"
    date = "date"
    gush_helka = "gush_helka"
    assessment_number = "assessment_number"
    bank_branch = "bank_branch"
    address = "address"
    phone = "phone"
    currency = "currency"
    enum = "enum"
    free_text = "free_text"


class PiiType(StrEnum):
    IL_ID = "IL_ID"
    PERSON = "PERSON"
    DATE = "DATE"
    LOCATION = "LOCATION"
    PHONE = "PHONE"
    OTHER = "OTHER"


class SourceKind(StrEnum):
    image = "image"
    pdf = "pdf"
    docx = "docx"


class ValueKind(StrEnum):
    printed = "printed"
    handwritten = "handwritten"
```

- [ ] **Step 2: Rewrite `contracts/template.py` (trim to BBox only)**

```python
from __future__ import annotations

from pydantic import BaseModel


class BBox(BaseModel):
    page: int = 1
    x: float
    y: float
    w: float
    h: float
```

- [ ] **Step 3: Rewrite `contracts/records.py`**

```python
from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field as PField


class Value(BaseModel):
    field_id: str
    value: str
    valid: bool = True


class Record(BaseModel):
    index: int
    values: dict[str, Value] = PField(default_factory=dict)
```

- [ ] **Step 4: Rewrite `contracts/state.py`**

```python
from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field as PField

from doc2tests.contracts.enums import FieldType, PiiType, SourceKind, ValueKind
from doc2tests.contracts.records import Record
from doc2tests.contracts.template import BBox


class InputRef(BaseModel):
    path: str
    kind: SourceKind


class ParsedField(BaseModel):
    label: str
    value: str
    value_kind: ValueKind = ValueKind.printed
    bbox: BBox | None = None


class ParseResult(BaseModel):
    raw_text: str = ""
    fields: list[ParsedField] = PField(default_factory=list)
    provider: str = ""


class DetectedValue(BaseModel):
    """A value found in the form, classified. Personal values get replaced."""
    id: str
    label: str
    value: str
    field_type: FieldType = FieldType.free_text
    is_personal: bool = False
    pii_type: PiiType | None = None
    value_kind: ValueKind = ValueKind.printed
    bbox: BBox | None = None


class ReviewDecision(BaseModel):
    """What the user confirmed in the review gate: the final (possibly edited /
    extended) set of detected values, replacing the machine detection."""
    approved: bool = False
    values: list[DetectedValue] = PField(default_factory=list)


class StageError(BaseModel):
    stage: str
    message: str


class RunConfig(BaseModel):
    n: int = 10
    seed: int = 42


class GraphState(BaseModel):
    input_ref: InputRef
    config: RunConfig = PField(default_factory=RunConfig)
    page_images: list[bytes] = PField(default_factory=list)
    parse_result: ParseResult | None = None
    detected: list[DetectedValue] = PField(default_factory=list)
    review: ReviewDecision | None = None
    population: list[Record] = PField(default_factory=list)
    output_images: list[bytes] = PField(default_factory=list)
    errors: list[StageError] = PField(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
```

### 4b. Detect → DetectedValue

- [ ] **Step 5: Write the failing test for detect**

Rewrite `tests/deid/test_detect.py`:

```python
from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import GraphState, InputRef, ParsedField, ParseResult
from doc2tests.deid.detect import detect_fields


def _state(fields):
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        parse_result=ParseResult(fields=fields),
    )


def test_detect_assigns_ids_types_and_personal_flag():
    st = _state([
        ParsedField(label="שם מלא", value="דנה כהן"),
        ParsedField(label="מספר זהות", value="123456782"),
        ParsedField(label="גוש", value="6941"),
    ])
    out = detect_fields(st)["detected"]
    by_label = {d.label: d for d in out}
    assert by_label["שם מלא"].field_type == FieldType.hebrew_name
    assert by_label["שם מלא"].is_personal is True
    assert by_label["מספר זהות"].field_type == FieldType.israeli_id
    assert by_label["מספר זהות"].is_personal is True
    assert by_label["גוש"].is_personal is False
    assert len({d.id for d in out}) == 3          # unique ids
    assert all(d.id for d in out)


def test_detect_passthrough_without_parse():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert detect_fields(st)["detected"] == []
```

- [ ] **Step 6: Rewrite `deid/detect.py`**

```python
from __future__ import annotations

from typing import Any

from doc2tests.common.slug import unique_slug
from doc2tests.contracts.state import DetectedValue, GraphState
from doc2tests.deid.classify import classify_value


def detect_fields(state: GraphState) -> dict[str, Any]:
    if state.parse_result is None:
        return {"detected": []}
    out: list[DetectedValue] = []
    seen: list[str] = []
    for pf in state.parse_result.fields:
        ftype, pii, pii_type = classify_value(pf.label, pf.value)
        fid = unique_slug(pf.label or pf.value or "field", seen)
        seen.append(fid)
        out.append(DetectedValue(
            id=fid, label=pf.label, value=pf.value, field_type=ftype,
            is_personal=pii, pii_type=pii_type, value_kind=pf.value_kind, bbox=pf.bbox,
        ))
    return {"detected": out}
```

### 4c. Generate valid-only

- [ ] **Step 7: Write the failing tests for strategies + population**

Rewrite `tests/generate/test_strategies.py`:

```python
import random

from doc2tests.contracts.enums import FieldType
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import validate


def test_every_typed_strategy_generates_a_valid_value():
    rng = random.Random(1)
    for ft in [FieldType.israeli_id, FieldType.date, FieldType.phone,
               FieldType.bank_branch, FieldType.gush_helka]:
        v = strategy_for(ft, rng).generate()
        assert validate(ft, v) is True, (ft, v)


def test_free_text_strategy_returns_nonempty():
    rng = random.Random(1)
    assert strategy_for(FieldType.free_text, rng).generate().strip()
```

Rewrite `tests/generate/test_population.py`:

```python
from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import DetectedValue, GraphState, InputRef, RunConfig
from doc2tests.generate.population import generate_population
from doc2tests.validators import validate


def _state(n):
    detected = [
        DetectedValue(id="pid", label="ת.ז", value="123456782",
                      field_type=FieldType.israeli_id, is_personal=True),
        DetectedValue(id="nm", label="שם", value="דנה כהן",
                      field_type=FieldType.hebrew_name, is_personal=True),
        DetectedValue(id="city", label="עיר", value="חיפה",
                      field_type=FieldType.free_text, is_personal=False),
    ]
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        detected=detected, config=RunConfig(n=n, seed=7),
    )


def test_population_has_exactly_n_records():
    out = generate_population(_state(10))["population"]
    assert len(out) == 10


def test_only_personal_fields_are_generated():
    rec = generate_population(_state(5))["population"][0]
    assert set(rec.values) == {"pid", "nm"}     # city (non-personal) not generated


def test_generated_values_are_valid():
    for rec in generate_population(_state(8))["population"]:
        assert validate(FieldType.israeli_id, rec.values["pid"].value) is True
        assert rec.values["pid"].valid is True


def test_deterministic_same_seed():
    a = generate_population(_state(6))["population"]
    b = generate_population(_state(6))["population"]
    assert [r.values["pid"].value for r in a] == [r.values["pid"].value for r in b]


def test_passthrough_without_detected():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert generate_population(st)["population"] == []
```

- [ ] **Step 8: Rewrite `generate/strategies.py`**

```python
from __future__ import annotations

import random
from typing import Protocol

from faker import Faker

from doc2tests.contracts.enums import FieldType
from doc2tests.validators.israeli_id import complete_israeli_id


class FieldStrategy(Protocol):
    def generate(self) -> str: ...


class _Base:
    def __init__(self, rng: random.Random):
        self.rng = rng


class IsraeliIdStrategy(_Base):
    def generate(self) -> str:
        prefix = "".join(str(self.rng.randint(0, 9)) for _ in range(8))
        return complete_israeli_id(prefix)


class DateStrategy(_Base):
    def generate(self) -> str:
        d = self.rng.randint(1, 28)
        m = self.rng.randint(1, 12)
        y = self.rng.randint(1960, 2024)
        return f"{d:02d}.{m:02d}.{y}"


class PhoneStrategy(_Base):
    def generate(self) -> str:
        return "05" + "".join(str(self.rng.randint(0, 9)) for _ in range(8))


class BankBranchStrategy(_Base):
    def generate(self) -> str:
        return f"{self.rng.randint(100, 999)}"


class GushHelkaStrategy(_Base):
    def generate(self) -> str:
        return f"{self.rng.randint(1000, 9999)}-{self.rng.randint(1, 999)}-0"


class NumberStrategy(_Base):
    def generate(self) -> str:
        return "".join(str(self.rng.randint(0, 9)) for _ in range(9))


class _FakerStrategy(_Base):
    _faker = Faker("he_IL")

    def __init__(self, rng: random.Random):
        super().__init__(rng)
        self._faker.seed_instance(rng.randint(0, 10_000_000))


class HebrewNameStrategy(_FakerStrategy):
    def generate(self) -> str:
        return str(self._faker.name())


class FreeTextStrategy(_FakerStrategy):
    def generate(self) -> str:
        return str(self._faker.sentence(nb_words=3))


_REGISTRY: dict[FieldType, type[_Base]] = {
    FieldType.israeli_id: IsraeliIdStrategy,
    FieldType.date: DateStrategy,
    FieldType.hebrew_name: HebrewNameStrategy,
    FieldType.phone: PhoneStrategy,
    FieldType.bank_branch: BankBranchStrategy,
    FieldType.gush_helka: GushHelkaStrategy,
    FieldType.assessment_number: NumberStrategy,
    FieldType.currency: NumberStrategy,
}


def strategy_for(field_type: FieldType, rng: random.Random) -> FieldStrategy:
    cls = _REGISTRY.get(field_type, FreeTextStrategy)
    return cls(rng)  # type: ignore[return-value]
```

- [ ] **Step 9: Rewrite `generate/population.py`**

```python
from __future__ import annotations

import random
from typing import Any

from doc2tests.common.logging import get_logger
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import DetectedValue, GraphState
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import validate

_log = get_logger("generate")


def _valid_value(field: DetectedValue, rng: random.Random, attempts: int = 8) -> str:
    """Generate a value that passes its validator (belt-and-suspenders retry)."""
    strat = strategy_for(field.field_type, rng)
    v = strat.generate()
    for _ in range(attempts):
        if validate(field.field_type, v):
            return v
        v = strat.generate()
    return v


def generate_population(state: GraphState) -> dict[str, Any]:
    personal = [d for d in state.detected if d.is_personal]
    if not personal:
        return {"population": []}
    rng = random.Random(state.config.seed)
    records: list[Record] = []
    for i in range(state.config.n):
        values = {
            d.id: Value(field_id=d.id, value=(nv := _valid_value(d, rng)),
                        valid=validate(d.field_type, nv))
            for d in personal
        }
        records.append(Record(index=i, values=values))
    _log.info("generated %d records for %d personal field(s)",
              len(records), len(personal))
    return {"population": records}
```

### 4d. Parse (drop docx-text branch; store page images)

- [ ] **Step 10: Rewrite `ingest/parse.py`**

Keep the vision prompt + `_parse_fields` (unchanged bodies); change routing to always rasterize + vision, and return `page_images`:

```python
from __future__ import annotations

from typing import Any

from doc2tests.common.json_utils import extract_json
from doc2tests.common.logging import get_logger
from doc2tests.contracts.enums import ValueKind
from doc2tests.contracts.state import GraphState, ParsedField, ParseResult, StageError
from doc2tests.contracts.template import BBox
from doc2tests.ingest.rasterize import rasterize
from doc2tests.providers.base import LLMProvider

_log = get_logger("ingest")

_SCHEMA = (
    'Return ONLY a JSON object with keys: '
    '"raw_text" (string, all visible text), and '
    '"fields" (array). Each field: '
    '{"label": <the printed field label, transcribed exactly>, '
    '"value": <the filled-in value, "" if blank>, '
    '"value_kind": "printed" | "handwritten", '
    '"bbox": {"page":1,"x":0..1,"y":0..1,"w":0..1,"h":0..1} | null }. '
    "Do not include commentary."
)
_COMPLETENESS = (
    "Extract EVERY piece of variable / filled-in information as a field — be exhaustive. "
    "This includes: the recipient/addressee block (person or company name, institution, "
    "full address, city, PO box), every id/reference/assessment/receipt number, all dates, "
    "amounts and sums, phone numbers, גוש/חלקה/תת-חלקה parcel numbers, names of parties "
    "(seller/buyer/applicant), and any handwritten or typed value. Treat anything that "
    "would change between two copies of this form as a value (not as a static label). "
    "Also include labelled fields that are currently blank. "
)
VISION_PROMPT = (
    "You are a meticulous Hebrew document OCR parser. Read this scanned/photographed "
    "form (Hebrew, right-to-left). Transcribe every label and value EXACTLY as written, "
    "preserving Hebrew spelling, punctuation and digits — do not paraphrase, translate, "
    "or guess plausible words. " + _COMPLETENESS +
    "The bbox is the value's approximate location, normalized 0..1 of the image "
    "(x,y = top-right of the value region for RTL); accuracy of transcription matters "
    "more than the bbox. " + _SCHEMA
)


def _bbox(raw: dict[str, Any] | None) -> BBox | None:
    if not raw:
        return None
    try:
        return BBox(page=int(raw.get("page", 1)), x=float(raw["x"]), y=float(raw["y"]),
                    w=float(raw["w"]), h=float(raw["h"]))
    except (KeyError, TypeError, ValueError):
        return None


def _parse_fields(text: str) -> tuple[str, list[ParsedField]]:
    data = extract_json(text)
    fields: list[ParsedField] = []
    for f in data.get("fields", []):
        kind = (ValueKind.handwritten if f.get("value_kind") == "handwritten"
                else ValueKind.printed)
        fields.append(ParsedField(
            label=str(f.get("label", "")), value=str(f.get("value", "")),
            value_kind=kind, bbox=_bbox(f.get("bbox")),
        ))
    return str(data.get("raw_text", "")), fields


def ingest_parse(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    """Rasterize any input to page images, then vision-extract its fields."""
    path = state.input_ref.path
    try:
        images = rasterize(path)
        resp = provider.extract_vision(images, VISION_PROMPT, json_mode=True)
        raw_text, fields = _parse_fields(resp.text)
        _log.info("ingest_parse: %d page(s) -> %d fields via %s",
                  len(images), len(fields), provider.name)
        return {
            "page_images": images,
            "parse_result": ParseResult(
                raw_text=raw_text, fields=fields, provider=provider.name),
        }
    except Exception as exc:  # noqa: BLE001 - node boundary converts errors to state
        _log.exception("ingest_parse failed for %s", path)
        return {
            "parse_result": ParseResult(provider=provider.name),
            "errors": [StageError(stage="ingest_parse", message=str(exc))],
        }
```

- [ ] **Step 11: Trim `ingest/loaders.py`** (keep `detect_kind`; drop `load_images` + `read_docx_text` + `_render_pdf_to_images`)

```python
"""Format detection. Rasterization lives in ingest/rasterize.py."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

Kind = Literal["image", "pdf", "docx"]

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def detect_kind(path: str) -> Kind:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".docx", ".doc"):
        return "docx"
    if ext in _IMAGE_EXT:
        return "image"
    raise ValueError(f"unsupported file type: {ext or path}")
```

- [ ] **Step 12: Update `tests/ingest/test_parse.py` + `tests/ingest/test_loaders.py`**

In `tests/ingest/test_loaders.py`, delete any test of `load_images` / `read_docx_text`; keep `detect_kind` tests. In `tests/ingest/test_parse.py`, make the fake provider's `extract_vision` return the JSON and patch `rasterize` so no real file is needed:

```python
from unittest.mock import patch

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMResponse


class _FakeProvider:
    name = "fake"

    def complete_text(self, *a, **k): return LLMResponse(text="{}")
    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text='{"raw_text":"t","fields":['
                                '{"label":"שם","value":"דנה","value_kind":"printed"}]}')
    def edit_image(self, *a, **k): return b""


def test_ingest_parse_rasterizes_then_extracts():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    with patch("doc2tests.ingest.parse.rasterize", return_value=[b"\x89PNG..."]):
        out = ingest_parse(st, _FakeProvider())
    assert out["page_images"] == [b"\x89PNG..."]
    assert out["parse_result"].fields[0].label == "שם"
```

### 4e. Graph + config

- [ ] **Step 13: Write the failing graph test**

Rewrite `tests/orchestrator/test_graph.py`:

```python
from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import DetectedValue, GraphState, InputRef, ReviewDecision
from doc2tests.orchestrator.graph import build_graph
from doc2tests.providers.base import LLMResponse


class _StubProvider:
    name = "stub"

    def complete_text(self, *a, **k): return LLMResponse(text="{}")
    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text='{"raw_text":"t","fields":['
                                '{"label":"מספר זהות","value":"123456789"}]}')
    def edit_image(self, image, prompt, **k): return b"EDITED:" + image


def test_graph_runs_end_to_end_with_review(tmp_path, monkeypatch):
    monkeypatch.setattr("doc2tests.ingest.parse.rasterize", lambda p: [b"IMG"])
    app = build_graph(_StubProvider())
    cfg = {"configurable": {"thread_id": "t1"}}
    init = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))

    # run up to the interrupt before review_gate
    app.invoke(init, cfg)
    snap = app.get_state(cfg)
    detected = snap.values["detected"]
    assert detected and detected[0].field_type.value == "israeli_id"

    # user approves the detected values
    app.update_state(cfg, {"review": ReviewDecision(approved=True, values=detected)})
    final = app.invoke(None, cfg)
    assert len(final["population"]) == final["config"].n
    assert len(final["output_images"]) == final["config"].n
    assert final["output_images"][0].startswith(b"EDITED:")
```

- [ ] **Step 14: Rewrite `orchestrator/graph.py`**

```python
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from doc2tests.common.logging import get_logger
from doc2tests.contracts.state import GraphState, StageError
from doc2tests.deid.detect import detect_fields
from doc2tests.generate.population import generate_population
from doc2tests.imagegen.edit import Replacement, edit_form_image
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMProvider

_log = get_logger("graph")


def review_gate(state: GraphState) -> dict[str, Any]:
    """Human-in-the-loop checkpoint. The UI captures the final reviewed values in
    state.review.values; they replace machine detection. Execution pauses BEFORE
    this node (interrupt_before)."""
    if state.review and state.review.values:
        return {"detected": state.review.values}
    return {}


def _edit_images_node(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    if not state.page_images or not state.population:
        return {}
    original = state.page_images[0]
    personal = [d for d in state.detected if d.is_personal]
    outputs: list[bytes] = []
    errors: list[StageError] = []
    for rec in state.population:
        reps = [Replacement(old=d.value, new=rec.values[d.id].value)
                for d in personal if d.id in rec.values]
        try:
            outputs.append(edit_form_image(original, reps, provider))
        except Exception as exc:  # noqa: BLE001 - per-image failure is non-fatal
            _log.exception("edit failed for record %d", rec.index)
            errors.append(StageError(stage="edit_images", message=str(exc)))
    _log.info("produced %d edited image(s)", len(outputs))
    return {"output_images": outputs, "errors": errors}


def build_graph(provider: LLMProvider) -> Any:
    """Compile the pivot workflow with a human review gate before generation.

    interrupt_before=["review_gate"] pauses once values are detected, so a person
    can confirm/add/edit them, then resume to generate + edit images.
    """
    g = StateGraph(GraphState)
    g.add_node("ingest_parse", lambda s: ingest_parse(s, provider))
    g.add_node("detect_fields", detect_fields)
    g.add_node("review_gate", review_gate)
    g.add_node("generate_population", generate_population)
    g.add_node("edit_images", lambda s: _edit_images_node(s, provider))

    g.add_edge(START, "ingest_parse")
    g.add_edge("ingest_parse", "detect_fields")
    g.add_edge("detect_fields", "review_gate")
    g.add_edge("review_gate", "generate_population")
    g.add_edge("generate_population", "edit_images")
    g.add_edge("edit_images", END)

    return g.compile(checkpointer=MemorySaver(), interrupt_before=["review_gate"])
```

- [ ] **Step 15: Update `orchestrator/config.py`** (single provider does vision + edit)

```python
from __future__ import annotations

import os

from doc2tests.providers.openai_provider import OpenAIProvider


def build_provider() -> OpenAIProvider:
    """OpenAI provider: extract_vision uses the vision model, edit_image uses
    gpt-image-2. One provider serves both. Requires OPENAI_API_KEY in the env."""
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    return OpenAIProvider(model=model)
```

### 4f. Delete rejected subsystems

- [ ] **Step 16: Delete dead source + tests**

```bash
git rm -r src/doc2tests/render src/doc2tests/template src/doc2tests/schema \
         src/doc2tests/coverage src/doc2tests/api src/doc2tests/ingest/ocr_boxes.py \
         src/doc2tests/generate/relations.py
git rm -r tests/render tests/template tests/schema tests/coverage \
         tests/generate/test_relations.py
```

- [ ] **Step 17: Fix remaining references**

Search for stale imports and delete/adjust the offending tests:

Run: `uv run python -c "import doc2tests.orchestrator.graph, doc2tests.ui.app" 2>&1 | tail -5` (ui may still be old — that's Task 5; ignore ui import errors here). Then:

Run: `grep -rl "CanonicalTemplate\|TestClass\|build_coverage\|render_fill\|extract_schema\|anchor_fields\|build_template\|ocr_boxes\|violate_order\|load_images\|read_docx_text\|CoverageReport\|RenderStrategy\|RelationOp" src tests`

For each hit outside `ui/app.py` (handled in Task 5): remove the dead test file or fix the import. Expected residual hits: `contracts/test_template.py` (delete it), `contracts/test_state.py` (rewrite — see Step 18), `contracts/test_enums.py` (rewrite — remove TestClass/RelationOp/RenderStrategy assertions).

- [ ] **Step 18: Rewrite `tests/contracts/test_state.py` + `test_enums.py`; delete `test_template.py`**

`tests/contracts/test_enums.py`:

```python
from doc2tests.contracts.enums import FieldType, PiiType, SourceKind, ValueKind


def test_enum_members_present():
    assert FieldType.israeli_id == "israeli_id"
    assert PiiType.IL_ID == "IL_ID"
    assert set(SourceKind) == {SourceKind.image, SourceKind.pdf, SourceKind.docx}
    assert ValueKind.handwritten == "handwritten"
```

`tests/contracts/test_state.py`:

```python
from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import (
    DetectedValue,
    GraphState,
    InputRef,
    ReviewDecision,
    RunConfig,
)


def test_graphstate_defaults():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert st.config.n == 10
    assert st.detected == [] and st.population == [] and st.output_images == []


def test_review_decision_carries_values():
    dv = DetectedValue(id="pid", label="ת.ז", value="1", field_type=FieldType.israeli_id,
                       is_personal=True)
    rd = ReviewDecision(approved=True, values=[dv])
    assert rd.values[0].id == "pid"


def test_runconfig_overrides():
    assert RunConfig(n=25, seed=1).n == 25
```

```bash
git rm tests/contracts/test_template.py
```

- [ ] **Step 19: Run the full offline suite**

Run: `uv run pytest -q -k "not live"`
Expected: PASS (0 failures). If `tests/extraction/test_pipeline.py` or `tests/coverage`-style leftovers reference removed symbols, delete or fix them (extraction pipeline test should target the new graph or be removed if redundant with `test_graph.py`).

- [ ] **Step 20: Commit**

```bash
git add -A
git commit -m "feat(core): pivot to image-edit pipeline (valid-only data, gpt-image-2 edit node); delete HTML-recreation/template/schema/coverage/api"
```

---

## Task 5: Streamlit UI rewrite

**Files:**
- Rewrite: `src/doc2tests/ui/app.py`
- Create: `src/doc2tests/ui/helpers.py` (pure, testable)
- Test: `tests/ui/__init__.py`, `tests/ui/test_helpers.py`

- [ ] **Step 1: Write the failing tests for pure helpers**

Create `tests/ui/__init__.py` (empty) and `tests/ui/test_helpers.py`:

```python
from doc2tests.contracts.records import Record, Value
from doc2tests.ui.helpers import records_to_rows, zip_images


def test_zip_images_returns_zip_bytes():
    data = zip_images([b"AAA", b"BBB"], prefix="form")
    assert data[:2] == b"PK"                       # zip magic
    import io, zipfile
    zf = zipfile.ZipFile(io.BytesIO(data))
    assert sorted(zf.namelist()) == ["form_1.png", "form_2.png"]


def test_records_to_rows_flattens_values():
    recs = [Record(index=0, values={"pid": Value(field_id="pid", value="123")})]
    rows = records_to_rows(recs)
    assert rows == [{"#": 1, "pid": "123"}]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/ui/test_helpers.py -v`
Expected: FAIL — module `doc2tests.ui.helpers` does not exist.

- [ ] **Step 3: Implement `ui/helpers.py`**

```python
from __future__ import annotations

import io
import zipfile

from doc2tests.contracts.records import Record


def zip_images(images: list[bytes], prefix: str = "form") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, img in enumerate(images, start=1):
            zf.writestr(f"{prefix}_{i}.png", img)
    return buf.getvalue()


def records_to_rows(records: list[Record]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for r in records:
        row: dict[str, object] = {"#": r.index + 1}
        for fid, v in r.values.items():
            row[fid] = v.value
        rows.append(row)
    return rows
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/ui/test_helpers.py -v`
Expected: PASS

- [ ] **Step 5: Rewrite `src/doc2tests/ui/app.py`**

```python
"""Streamlit UI for the image-edit pipeline (RTL, Hebrew).

Flow: upload form -> detect values -> review/add/pick N -> generate valid variants
-> gpt-image-2 edits the original per variant -> download images.
Run: uv run streamlit run src/doc2tests/ui/app.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from doc2tests.common.logging import recent_logs
from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import (
    DetectedValue,
    GraphState,
    InputRef,
    ReviewDecision,
)
from doc2tests.ingest.loaders import detect_kind
from doc2tests.orchestrator.config import build_provider
from doc2tests.orchestrator.graph import build_graph
from doc2tests.ui.helpers import records_to_rows, zip_images

load_dotenv()

st.set_page_config(page_title="מחולל טפסים", layout="wide")
st.markdown(
    "<style>body,.stApp{direction:rtl;text-align:right}"
    ".stDataFrame{direction:rtl}</style>", unsafe_allow_html=True)

_STEPS = ["העלאה", "זיהוי ערכים", "סקירה ואישור", "יצירה ומילוי", "הורדה"]


def _stepper(active: int) -> None:
    cols = st.columns(len(_STEPS))
    for i, (c, name) in enumerate(zip(cols, _STEPS, strict=True)):
        mark = "✅" if i < active else ("🔵" if i == active else "⚪")
        c.markdown(f"{mark} **{name}**")


def _save_upload(uploaded) -> str:
    suffix = Path(uploaded.name).suffix
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded.getbuffer())
    return path


def _thread_cfg() -> dict:
    return {"configurable": {"thread_id": st.session_state["thread_id"]}}


def main() -> None:
    st.title("מחולל טפסים — החלפת ערכים בתמונה")
    if "phase" not in st.session_state:
        st.session_state["phase"] = "upload"

    phase = st.session_state["phase"]
    _stepper({"upload": 0, "review": 2, "done": 4}[phase])

    if not os.getenv("OPENAI_API_KEY"):
        st.error("חסר OPENAI_API_KEY בקובץ .env")
        return

    if phase == "upload":
        _upload_phase()
    elif phase == "review":
        _review_phase()
    elif phase == "done":
        _done_phase()

    with st.sidebar.expander("לוגים", expanded=False):
        st.code("\n".join(recent_logs(120)) or "—")


def _upload_phase() -> None:
    uploaded = st.file_uploader("העלה טופס", type=["jpg", "jpeg", "png", "pdf", "docx"])
    if uploaded and st.button("זהה ערכים", type="primary"):
        path = _save_upload(uploaded)
        st.session_state["thread_id"] = uploaded.name
        app = build_graph(build_provider())
        init = GraphState(
            input_ref=InputRef(path=path, kind=SourceKind(detect_kind(path))))
        with st.spinner("מזהה ערכים..."):
            app.invoke(init, _thread_cfg())
        st.session_state["app"] = app
        snap = app.get_state(_thread_cfg())
        st.session_state["detected"] = [d.model_dump() for d in snap.values["detected"]]
        st.session_state["page_images"] = snap.values["page_images"]
        st.session_state["phase"] = "review"
        st.rerun()


def _review_phase() -> None:
    imgs = st.session_state.get("page_images") or []
    if imgs:
        st.image(imgs[0], caption="הטופס שנקלט", width=380)

    st.subheader("ערכים שזוהו — אשר, ערוך, או הוסף")
    st.caption("סמן 'אישי?' לכל ערך שיש להחליף. הוסף שורות לערכים שלא זוהו.")
    rows = [
        {"label": d["label"], "value": d["value"],
         "field_type": d["field_type"], "אישי?": d["is_personal"]}
        for d in st.session_state["detected"]
    ]
    edited = st.data_editor(
        rows, num_rows="dynamic", use_container_width=True,
        column_config={
            "field_type": st.column_config.SelectboxColumn(
                "סוג", options=[t.value for t in FieldType]),
            "אישי?": st.column_config.CheckboxColumn("אישי?"),
        },
    )
    n = st.number_input("כמה וריאציות ליצור?", min_value=1, max_value=50, value=10)

    if st.button("צור טפסים", type="primary"):
        from doc2tests.common.slug import unique_slug
        values: list[DetectedValue] = []
        seen: list[str] = []
        for r in edited:
            label = str(r.get("label", "")).strip()
            val = str(r.get("value", "")).strip()
            if not label and not val:
                continue
            fid = unique_slug(label or val, seen)
            seen.append(fid)
            values.append(DetectedValue(
                id=fid, label=label, value=val,
                field_type=FieldType(r.get("field_type") or "free_text"),
                is_personal=bool(r.get("אישי?")),
            ))
        app = st.session_state["app"]
        cfg = _thread_cfg()
        app.update_state(cfg, {
            "review": ReviewDecision(approved=True, values=values),
            "config": {"n": int(n), "seed": 42},
        })
        with st.spinner(f"מייצר {int(n)} טפסים..."):
            final = app.invoke(None, cfg)
        st.session_state["population"] = [r.model_dump() for r in
                                          _as_records(final["population"])]
        st.session_state["output_images"] = final["output_images"]
        st.session_state["errors"] = [e.message for e in final.get("errors", [])]
        st.session_state["phase"] = "done"
        st.rerun()


def _as_records(pop):
    from doc2tests.contracts.records import Record
    return [p if isinstance(p, Record) else Record(**p) for p in pop]


def _done_phase() -> None:
    imgs = st.session_state.get("output_images") or []
    errs = st.session_state.get("errors") or []
    st.success(f"נוצרו {len(imgs)} טפסים.")
    if errs:
        st.warning(f"{len(errs)} כשלו: " + "; ".join(errs[:3]))

    from doc2tests.contracts.records import Record
    recs = [Record(**p) for p in st.session_state.get("population", [])]
    if recs:
        with st.expander("הערכים שנוצרו (מאומתים)"):
            st.dataframe(records_to_rows(recs), use_container_width=True)

    if imgs:
        st.download_button("הורד הכל (zip)", zip_images(imgs),
                           file_name="forms.zip", mime="application/zip")
        cols = st.columns(3)
        for i, img in enumerate(imgs):
            c = cols[i % 3]
            c.image(img, caption=f"טופס {i + 1}", use_container_width=True)
            c.download_button("הורד", img, file_name=f"form_{i + 1}.png",
                              mime="image/png", key=f"dl_{i}")

    if st.button("התחל מחדש"):
        for k in ("phase", "app", "detected", "page_images", "population",
                  "output_images", "errors", "thread_id"):
            st.session_state.pop(k, None)
        st.rerun()


if __name__ == "__main__":
    main()
main()
```

Note: the trailing `main()` (outside `__main__`) is required so `streamlit run` executes it. Keep both lines.

- [ ] **Step 6: Smoke-check the UI imports cleanly**

Run: `uv run python -c "import importlib; importlib.import_module('doc2tests.ui.app')" 2>&1 | tail -5`
Expected: no ImportError (Streamlit executing `main()` may warn about missing `ScriptRunContext` — that is fine; only ImportError/NameError is a failure).

- [ ] **Step 7: Run UI helper tests**

Run: `uv run pytest tests/ui/ -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/doc2tests/ui tests/ui
git commit -m "feat(ui): rewrite Streamlit app for image-edit flow (upload/review/generate/download)"
```

---

## Task 6: Dependency + config cleanup and final verification

**Files:**
- Modify: `pyproject.toml`
- Test: whole suite + mypy + ruff

- [ ] **Step 1: Prune `pyproject.toml` dependencies**

Replace the `dependencies` list with only what the pivot uses:

```toml
dependencies = [
    "pydantic>=2.7",
    "python-dotenv>=1.0",
    "openai>=2.44",
    "requests>=2.32",
    "faker>=40.28.1",
    "langgraph>=1.2.8",
    "streamlit>=1.59.1",
    "pymupdf>=1.28.0",
    "pillow>=12.3.0",
    "python-docx>=1.2.0",
]
```

(`python-docx` stays only for the rasterize test that authors a `.docx` fixture. Removed: `jinja2`, `docxtpl`, `pytesseract`, `fastapi`, `uvicorn`, `python-multipart`.)

- [ ] **Step 2: Prune ruff + mypy config**

In `pyproject.toml`, remove the `[tool.ruff.lint.per-file-ignores]` block (the `api/main.py` file is gone) and update the mypy overrides to drop deleted modules:

```toml
[[tool.mypy.overrides]]
module = ["docx.*", "fitz"]
ignore_missing_imports = true
```

- [ ] **Step 3: Sync the environment**

Run: `uv sync --extra dev`
Expected: resolves without the removed packages.

- [ ] **Step 4: Run the full offline test suite**

Run: `uv run pytest -q -k "not live"`
Expected: PASS, 0 failures.

- [ ] **Step 5: Run mypy (strict) and ruff**

Run: `uv run mypy && uv run ruff check src tests`
Expected: both clean. Fix any type/lint fallout (e.g. add `# type: ignore` only where an untyped third-party call is unavoidable; prefer real fixes).

- [ ] **Step 6: Update the live e2e/extraction tests to the new API (or skip cleanly)**

Open `tests/extraction/test_live_openai.py` and `tests/orchestrator/test_live_e2e.py`. Update them to call `build_graph(build_provider())` with the review-gate resume pattern from Task 4 Step 13, and assert `output_images` is non-empty PNG. Keep the `@pytest.mark.skipif(not OPENAI_API_KEY)` guard. Do not run them in CI-less mode.

- [ ] **Step 7: Live smoke (manual, optional — costs money)**

Run: `uv run pytest tests/orchestrator/test_live_e2e.py -v` (only if you want to spend a real gpt-image-2 call). Expected: 1 passed, output image is a valid PNG.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock tests/extraction tests/orchestrator
git commit -m "chore: prune deps/config for image-edit pivot; update live tests"
```

---

## Self-Review Notes (author)

- **Spec coverage:** ingest image/pdf/word (Task 3) ✓; detect values (Task 4b) ✓; review/add/N gate (Task 4e graph + Task 5 UI) ✓; valid-only generation (Task 4c) ✓; gpt-image-2 edit with input_fidelity=high (Task 1) + strong prompt (Task 2) ✓; download individual + zip (Task 5) ✓; logging (existing logger reused in every new node) ✓; delete rejected subsystems (Task 4f) ✓; pruning deps (Task 6) ✓.
- **Reconciliation:** the spec mentioned keeping `generate/relations.py` for date ordering, but relation inference (schema/infer, template) is deleted; with no source of relations, cross-field ordering is dropped (YAGNI) and each field is independently valid. This plan deletes `relations.py`. Recorded here as the intentional deviation.
- **Type consistency:** `DetectedValue` fields (`id, label, value, field_type, is_personal, pii_type, value_kind, bbox`) used identically in detect, graph, and UI. `Replacement(old, new)` used identically in imagegen and graph. `edit_image(image, prompt, *, mask, size, quality)` signature identical across protocol + OpenAI + Ollama + stub providers.
- **Masking:** retained `mask` param end-to-end but unused in v1 (future escalation), matching spec §2/§10.
```

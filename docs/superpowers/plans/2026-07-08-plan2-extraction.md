# Extraction Implementation Plan (Plan 2 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a document image into a validated `CanonicalTemplate` — the four extraction nodes F1 (ingest & parse), F2 (field detection / de-id), F3 (build template), F4 (schema inference) — each a pure `GraphState -> partial GraphState` function, offline-testable via injected fake providers.

**Architecture:** F1 asks a vision provider for structured JSON (raw text + labeled fields + value_kind + optional bbox). F2 classifies each parsed field into a semantic `FieldType`, flags PII, and augments with Israeli recognizers (ID checksum promotes a numeric field to `israeli_id`). F3 assembles the `CanonicalTemplate` (stable slug ids, placeholders, constraints from field type). F4 infers cross-field relations (date ordering) and per-field notes, then re-validates the template. Every node returns a partial-state dict; a thin JSON-repair helper tolerates model quirks.

**Tech Stack:** Builds on Plan 1 (`contracts`, `providers`, `validators`). Adds no third-party deps.

**Depends on:** Plan 1 complete (contracts, providers, validators, 45 tests green).

**Note on git:** Local commits are checkpoints (no remote/push).

---

## File Structure

```
src/doc2tests/
├── common/
│   ├── __init__.py
│   ├── json_utils.py          # extract_json(text) -> dict  (strip fences, first {...})
│   └── slug.py                # slugify(label) -> stable ascii id
├── ingest/
│   ├── __init__.py
│   └── parse.py               # F1: ingest_parse(state, provider) -> dict
├── deid/
│   ├── __init__.py
│   ├── classify.py            # value -> FieldType + pii heuristics
│   └── detect.py              # F2: detect_fields(state) -> dict
├── template/
│   ├── __init__.py
│   └── build.py               # F3: build_template(state) -> dict
└── schema/
    ├── __init__.py
    └── infer.py               # F4: extract_schema(state) -> dict
tests/
├── common/
├── ingest/
├── deid/
├── template/
├── schema/
└── extraction/                # integration: fake-provider full F1..F4 chain
```

---

## Task 1: common/json_utils.py — tolerant JSON extraction

Vision/LLM output may wrap JSON in ```` ```json ```` fences or prose. `extract_json` returns the first balanced top-level object.

**Files:**
- Create: `src/doc2tests/common/__init__.py`, `src/doc2tests/common/json_utils.py`
- Test: `tests/common/test_json_utils.py`

- [ ] **Step 1: Write the failing test**

`tests/common/test_json_utils.py`:
```python
import pytest

from doc2tests.common.json_utils import extract_json


def test_plain_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_strips_code_fence():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_ignores_prose_around_object():
    assert extract_json('Here you go:\n{"a": [1, 2]}\nThanks') == {"a": [1, 2]}


def test_handles_nested_braces():
    assert extract_json('{"a": {"b": 1}}') == {"a": {"b": 1}}


def test_raises_on_no_object():
    with pytest.raises(ValueError):
        extract_json("no json here")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/common/test_json_utils.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/common/__init__.py` (empty).
`src/doc2tests/common/json_utils.py`:
```python
from __future__ import annotations

import json
from typing import Any


def extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        result = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(result, dict):
                        return result
                    break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in text")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/common/test_json_utils.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit (local)**

```bash
mkdir -p tests/common && touch tests/common/__init__.py
git add -A && git commit -q -m "feat(common): tolerant JSON object extraction"
```

---

## Task 2: common/slug.py — stable field ids

**Files:**
- Create: `src/doc2tests/common/slug.py`
- Test: `tests/common/test_slug.py`

- [ ] **Step 1: Write the failing test**

`tests/common/test_slug.py`:
```python
from doc2tests.common.slug import slugify, unique_slug


def test_ascii_lowercase_underscores():
    assert slugify("Primary Applicant ID") == "primary_applicant_id"


def test_hebrew_label_falls_back_to_transliteration_marker():
    # non-ascii label yields a non-empty ascii slug
    s = slugify("מספר זהות")
    assert s and all(c.isalnum() or c == "_" for c in s)


def test_unique_slug_disambiguates_collisions():
    seen = {"entry_date"}
    assert unique_slug("Entry Date", seen) == "entry_date_2"
    seen.add("entry_date_2")
    assert unique_slug("Entry Date", seen) == "entry_date_3"


def test_empty_label_gets_field_prefix():
    assert slugify("").startswith("field")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/common/test_slug.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/common/slug.py`:
```python
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

_NON_ASCII = re.compile(r"[^a-z0-9]+")


def _stable_suffix(label: str) -> int:
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()
    return int(digest[:4], 16) % 10000


def slugify(label: str) -> str:
    ascii_only = label.strip().lower().encode("ascii", "ignore").decode("ascii")
    slug = _NON_ASCII.sub("_", ascii_only).strip("_")
    return slug or f"field_{_stable_suffix(label)}"


def unique_slug(label: str, seen: Iterable[str]) -> str:
    seen_set = set(seen)
    base = slugify(label)
    if base not in seen_set:
        return base
    i = 2
    while f"{base}_{i}" in seen_set:
        i += 1
    return f"{base}_{i}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/common/test_slug.py -v`
Expected: PASS (4 tests)

Note: `slugify("")` returns `field_<n>` where n is a stable sha1-derived number (deterministic across runs); the test only asserts the `field` prefix.

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(common): stable slug ids with collision disambiguation"
```

---

## Task 3: ingest/parse.py — F1 vision parse

The node takes `GraphState` + an `LLMProvider`, reads the image bytes, calls `extract_vision` with a fixed JSON prompt, and returns `{"parse_result": ParseResult(...)}`. On any failure it returns `{"errors": [StageError(...)]}` and an empty parse result.

**Files:**
- Create: `src/doc2tests/ingest/__init__.py`, `src/doc2tests/ingest/parse.py`
- Test: `tests/ingest/test_parse.py`

- [ ] **Step 1: Write the failing test**

`tests/ingest/test_parse.py`:
```python
import json

from doc2tests.contracts.enums import SourceKind, ValueKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMResponse


class _FakeProvider:
    name = "fake"

    def __init__(self, payload: dict):
        self._payload = payload
        self.saw_images = None

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("F1 must use vision")

    def extract_vision(self, images, prompt, *, json_mode=False):
        self.saw_images = images
        return LLMResponse(text=json.dumps(self._payload))


def _state(tmp_path) -> GraphState:
    img = tmp_path / "d.jpeg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    return GraphState(input_ref=InputRef(path=str(img), kind=SourceKind.image))


def test_parse_populates_fields(tmp_path):
    provider = _FakeProvider({
        "raw_text": "בקשה",
        "fields": [
            {"label": "מספר זהות", "value": "123456782", "value_kind": "handwritten"},
            {"label": "תאריך כניסה", "value": "31.10.21", "value_kind": "printed"},
        ],
    })
    out = ingest_parse(_state(tmp_path), provider)
    pr = out["parse_result"]
    assert pr.provider == "fake"
    assert len(pr.fields) == 2
    assert pr.fields[0].value == "123456782"
    assert pr.fields[0].value_kind == ValueKind.handwritten
    assert provider.saw_images and isinstance(provider.saw_images[0], bytes)


def test_parse_records_error_on_bad_json(tmp_path):
    class _Bad(_FakeProvider):
        def extract_vision(self, images, prompt, *, json_mode=False):
            return LLMResponse(text="the model refused")

    out = ingest_parse(_state(tmp_path), _Bad({}))
    assert out["parse_result"].fields == []
    assert out["errors"][0].stage == "ingest_parse"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ingest/test_parse.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/ingest/__init__.py` (empty).
`src/doc2tests/ingest/parse.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from doc2tests.common.json_utils import extract_json
from doc2tests.contracts.enums import ValueKind
from doc2tests.contracts.state import GraphState, ParsedField, ParseResult, StageError
from doc2tests.contracts.template import BBox
from doc2tests.providers.base import LLMProvider

VISION_PROMPT = (
    "You are a document parser. Read this scanned/photographed form (Hebrew, RTL). "
    "Return ONLY a JSON object with keys: "
    '"raw_text" (string, all visible text), and '
    '"fields" (array). Each field: '
    '{"label": <the printed field label>, "value": <the filled-in value, "" if blank>, '
    '"value_kind": "printed" | "handwritten", '
    '"bbox": {"page":1,"x":0..1,"y":0..1,"w":0..1,"h":0..1} | null }. '
    "Do not include commentary."
)


def _bbox(raw: dict[str, Any] | None) -> BBox | None:
    if not raw:
        return None
    try:
        return BBox(page=int(raw.get("page", 1)), x=float(raw["x"]), y=float(raw["y"]),
                    w=float(raw["w"]), h=float(raw["h"]))
    except (KeyError, TypeError, ValueError):
        return None


def ingest_parse(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    try:
        image_bytes = Path(state.input_ref.path).read_bytes()
        resp = provider.extract_vision([image_bytes], VISION_PROMPT, json_mode=True)
        data = extract_json(resp.text)
        fields = []
        for f in data.get("fields", []):
            kind = ValueKind.handwritten if f.get("value_kind") == "handwritten" else ValueKind.printed
            fields.append(ParsedField(
                label=str(f.get("label", "")),
                value=str(f.get("value", "")),
                value_kind=kind,
                bbox=_bbox(f.get("bbox")),
            ))
        return {"parse_result": ParseResult(
            raw_text=str(data.get("raw_text", "")), fields=fields, provider=provider.name)}
    except Exception as exc:  # noqa: BLE001 - node boundary converts errors to state
        return {
            "parse_result": ParseResult(provider=provider.name),
            "errors": [StageError(stage="ingest_parse", message=str(exc))],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ingest/test_parse.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit (local)**

```bash
mkdir -p tests/ingest && touch tests/ingest/__init__.py
git add -A && git commit -q -m "feat(ingest): F1 vision parse node"
```

---

## Task 4: deid/classify.py — value -> FieldType + PII flag

Pure heuristics, no model. Uses Plan 1 validators to promote types (a 9-digit value with a valid checksum is `israeli_id`).

**Files:**
- Create: `src/doc2tests/deid/__init__.py`, `src/doc2tests/deid/classify.py`
- Test: `tests/deid/test_classify.py`

- [ ] **Step 1: Write the failing test**

`tests/deid/test_classify.py`:
```python
from doc2tests.contracts.enums import FieldType, PiiType
from doc2tests.deid.classify import classify_value


def test_valid_israeli_id_detected():
    ft, pii, pii_type = classify_value("מספר זהות", "123456782")
    assert ft == FieldType.israeli_id
    assert pii is True
    assert pii_type == PiiType.IL_ID


def test_date_detected():
    ft, _, _ = classify_value("תאריך כניסה", "31.10.21")
    assert ft == FieldType.date


def test_gush_helka_detected_by_label():
    ft, _, _ = classify_value("גוש חלקה", "9007-12-0")
    assert ft == FieldType.gush_helka


def test_phone_detected():
    ft, _, _ = classify_value("טלפון", "04-6327888")
    assert ft == FieldType.phone


def test_hebrew_name_by_label_keyword():
    ft, pii, _ = classify_value("שם משפחה", "כהן")
    assert ft == FieldType.hebrew_name
    assert pii is True


def test_default_free_text():
    ft, pii, _ = classify_value("הערות", "בקשה כללית")
    assert ft == FieldType.free_text
    assert pii is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/deid/test_classify.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/deid/__init__.py` (empty).
`src/doc2tests/deid/classify.py`:
```python
from __future__ import annotations

from doc2tests.contracts.enums import FieldType, PiiType
from doc2tests.validators import (
    is_valid_gush_helka,
    is_valid_il_date,
    is_valid_il_phone,
    is_valid_israeli_id,
)

_NAME_HINTS = ("שם", "name")
_ID_HINTS = ("זהות", "ת.ז", 'ת"ז', "id")
_DATE_HINTS = ("תאריך", "date")
_GUSH_HINTS = ("גוש", "חלקה", "gush")
_PHONE_HINTS = ("טלפון", "phone", "נייד")
_BRANCH_HINTS = ("סניף", "branch")
_ASSESS_HINTS = ("שומה", "assessment")


def _has(label: str, hints: tuple[str, ...]) -> bool:
    low = label.lower()
    return any(h.lower() in low for h in hints)


def classify_value(label: str, value: str) -> tuple[FieldType, bool, PiiType | None]:
    v = value.strip()
    # strongest signal: content validators
    if v and is_valid_israeli_id(v) and (_has(label, _ID_HINTS) or len(v.replace(" ", "")) == 9):
        return FieldType.israeli_id, True, PiiType.IL_ID
    if v and _has(label, _GUSH_HINTS) and is_valid_gush_helka(v):
        return FieldType.gush_helka, False, None
    if v and _has(label, _PHONE_HINTS) and is_valid_il_phone(v):
        return FieldType.phone, True, PiiType.PHONE
    if v and (is_valid_il_date(v) and _has(label, _DATE_HINTS)):
        return FieldType.date, False, PiiType.DATE
    if _has(label, _ASSESS_HINTS):
        return FieldType.assessment_number, False, None
    if _has(label, _BRANCH_HINTS):
        return FieldType.bank_branch, False, None
    if _has(label, _NAME_HINTS):
        return FieldType.hebrew_name, True, PiiType.PERSON
    return FieldType.free_text, False, None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/deid/test_classify.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit (local)**

```bash
mkdir -p tests/deid && touch tests/deid/__init__.py
git add -A && git commit -q -m "feat(deid): field classification heuristics"
```

---

## Task 5: deid/detect.py — F2 detect_fields node

Maps each `ParsedField` -> `DetectedField` via `classify_value`, preserving `value_kind` and `bbox`.

**Files:**
- Create: `src/doc2tests/deid/detect.py`
- Test: `tests/deid/test_detect.py`

- [ ] **Step 1: Write the failing test**

`tests/deid/test_detect.py`:
```python
from doc2tests.contracts.enums import FieldType, SourceKind, ValueKind
from doc2tests.contracts.state import GraphState, InputRef, ParsedField, ParseResult
from doc2tests.deid.detect import detect_fields


def _state_with(parsed):
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        parse_result=ParseResult(fields=parsed, provider="fake"),
    )


def test_detect_maps_types_and_pii():
    st = _state_with([
        ParsedField(label="מספר זהות", value="123456782", value_kind=ValueKind.handwritten),
        ParsedField(label="הערות", value="טקסט"),
    ])
    out = detect_fields(st)
    detected = out["detected_fields"]
    assert detected[0].type == FieldType.israeli_id
    assert detected[0].pii is True
    assert detected[0].value_kind == ValueKind.handwritten
    assert detected[1].type == FieldType.free_text


def test_detect_empty_when_no_parse_result():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    out = detect_fields(st)
    assert out["detected_fields"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/deid/test_detect.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/deid/detect.py`:
```python
from __future__ import annotations

from typing import Any

from doc2tests.contracts.state import DetectedField, GraphState
from doc2tests.deid.classify import classify_value


def detect_fields(state: GraphState) -> dict[str, Any]:
    if state.parse_result is None:
        return {"detected_fields": []}
    detected: list[DetectedField] = []
    for pf in state.parse_result.fields:
        ftype, pii, pii_type = classify_value(pf.label, pf.value)
        detected.append(DetectedField(
            label=pf.label, value=pf.value, type=ftype, pii=pii, pii_type=pii_type,
            value_kind=pf.value_kind, bbox=pf.bbox,
        ))
    return {"detected_fields": detected}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/deid/test_detect.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(deid): F2 detect_fields node"
```

---

## Task 6: template/build.py — F3 build_template node

Builds the `CanonicalTemplate`: stable slug ids, constraints derived from type (israeli_id -> checksum+length; required when a value was present), and `render_strategy = overlay` if any field has a bbox else `reconstruct`.

**Files:**
- Create: `src/doc2tests/template/__init__.py`, `src/doc2tests/template/build.py`
- Test: `tests/template/test_build.py`

- [ ] **Step 1: Write the failing test**

`tests/template/test_build.py`:
```python
from doc2tests.contracts.enums import FieldType, RenderStrategy, SourceKind, ValueKind
from doc2tests.contracts.state import DetectedField, GraphState, InputRef
from doc2tests.contracts.template import BBox
from doc2tests.template.build import build_template


def _state(detected):
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        detected_fields=detected,
    )


def test_build_assigns_slugs_and_constraints():
    st = _state([
        DetectedField(label="Primary Applicant ID", value="123456782",
                      type=FieldType.israeli_id, pii=True, value_kind=ValueKind.handwritten),
    ])
    out = build_template(st)
    tmpl = out["template"]
    f = tmpl.fields[0]
    assert f.id == "primary_applicant_id"
    assert f.placeholder == "{{ primary_applicant_id }}"
    assert f.constraints.checksum == "israeli_id"
    assert f.constraints.length == 9
    assert f.constraints.required is True


def test_duplicate_labels_get_unique_ids():
    st = _state([
        DetectedField(label="מספר זהות", value="123456782", type=FieldType.israeli_id),
        DetectedField(label="מספר זהות", value="318444973", type=FieldType.israeli_id),
    ])
    ids = [f.id for f in build_template(st)["template"].fields]
    assert len(ids) == len(set(ids))


def test_render_strategy_overlay_when_bbox_present():
    st = _state([
        DetectedField(label="שם", value="כהן", type=FieldType.hebrew_name,
                      bbox=BBox(page=1, x=0.1, y=0.1, w=0.2, h=0.03)),
    ])
    assert build_template(st)["template"].source.render_strategy == RenderStrategy.overlay


def test_render_strategy_reconstruct_when_no_bbox():
    st = _state([DetectedField(label="שם", value="כהן", type=FieldType.hebrew_name)])
    assert build_template(st)["template"].source.render_strategy == RenderStrategy.reconstruct
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/template/test_build.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/template/__init__.py` (empty).
`src/doc2tests/template/build.py`:
```python
from __future__ import annotations

from typing import Any

from doc2tests.common.slug import unique_slug
from doc2tests.contracts.enums import FieldType, RenderStrategy
from doc2tests.contracts.state import DetectedField, GraphState
from doc2tests.contracts.template import (
    CanonicalTemplate,
    Constraints,
    DocSource,
    Field,
)


def _constraints(df: DetectedField) -> Constraints:
    required = bool(df.value.strip())
    if df.type == FieldType.israeli_id:
        return Constraints(required=required, checksum="israeli_id", length=9)
    if df.type == FieldType.gush_helka:
        return Constraints(required=required, checksum="gush_helka")
    if df.type == FieldType.date:
        return Constraints(required=required, checksum="date")
    if df.type == FieldType.phone:
        return Constraints(required=required, checksum="phone")
    if df.type == FieldType.bank_branch:
        return Constraints(required=required, checksum="bank_branch")
    return Constraints(required=required)


def build_template(state: GraphState, doc_type: str = "generic-document") -> dict[str, Any]:
    seen: set[str] = set()
    fields: list[Field] = []
    for df in state.detected_fields:
        fid = unique_slug(df.label, seen)
        seen.add(fid)
        fields.append(Field(
            id=fid, label=df.label, type=df.type, value_kind=df.value_kind,
            pii=df.pii, pii_type=df.pii_type, constraints=_constraints(df), bbox=df.bbox,
        ))
    strategy = (RenderStrategy.overlay if any(f.bbox for f in fields)
                else RenderStrategy.reconstruct)
    template = CanonicalTemplate(
        doc_type=doc_type,
        source=DocSource(kind=state.input_ref.kind, pages=1, render_strategy=strategy),
        fields=fields,
    )
    return {"template": template}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/template/test_build.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit (local)**

```bash
mkdir -p tests/template && touch tests/template/__init__.py
git add -A && git commit -q -m "feat(template): F3 build canonical template node"
```

---

## Task 7: schema/infer.py — F4 relation + note inference

Deterministic pass that adds date-ordering relations between date fields (earlier-sounding label <= later) and records per-field notes. Re-validates the template through `CanonicalTemplate` (integrity holds because relation endpoints are existing field ids).

**Files:**
- Create: `src/doc2tests/schema/__init__.py`, `src/doc2tests/schema/infer.py`
- Test: `tests/schema/test_infer.py`

- [ ] **Step 1: Write the failing test**

`tests/schema/test_infer.py`:
```python
from doc2tests.contracts.enums import FieldType, RelationOp, SourceKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.contracts.template import (
    CanonicalTemplate,
    DocSource,
    Field,
)
from doc2tests.schema.infer import extract_schema


def _state_with_template(fields):
    tmpl = CanonicalTemplate(
        doc_type="d",
        source=DocSource(kind=SourceKind.image),
        fields=fields,
    )
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        template=tmpl,
    )


def test_adds_order_relation_between_two_dates():
    st = _state_with_template([
        Field(id="contract_date", label="תאריך חתימת חוזה", type=FieldType.date),
        Field(id="entry_date", label="תאריך כניסה לדירה", type=FieldType.date),
    ])
    out = extract_schema(st)
    tmpl = out["template"]
    rels = [r for r in tmpl.relations if r.kind == "order"]
    assert len(rels) == 1
    assert rels[0].op == RelationOp.le
    assert {rels[0].left, rels[0].right} == {"contract_date", "entry_date"}


def test_schema_notes_cover_every_field():
    st = _state_with_template([
        Field(id="a_id", label="מספר זהות", type=FieldType.israeli_id),
    ])
    out = extract_schema(st)
    assert "a_id" in out["field_schema"].notes


def test_no_relation_with_single_date():
    st = _state_with_template([
        Field(id="only_date", label="תאריך", type=FieldType.date),
    ])
    out = extract_schema(st)
    assert [r for r in out["template"].relations if r.kind == "order"] == []


def test_passthrough_when_no_template():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    out = extract_schema(st)
    assert out["template"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/schema/test_infer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/schema/__init__.py` (empty).
`src/doc2tests/schema/infer.py`:
```python
from __future__ import annotations

from typing import Any

from doc2tests.contracts.enums import FieldType, RelationOp
from doc2tests.contracts.state import FieldSchema, GraphState
from doc2tests.contracts.template import CanonicalTemplate, Field, Relation

# label keywords that imply a start point vs an end point
_START_HINTS = ("חתימת", "חוזה", "התחלה", "start", "from")
_END_HINTS = ("כניסה", "סיום", "end", "to")


def _rank(field: Field) -> int:
    low = field.label.lower()
    if any(h.lower() in low for h in _START_HINTS):
        return 0
    if any(h.lower() in low for h in _END_HINTS):
        return 2
    return 1


def _date_order_relations(fields: list[Field]) -> list[Relation]:
    dates = [f for f in fields if f.type == FieldType.date]
    if len(dates) < 2:
        return []
    ordered = sorted(dates, key=_rank)
    relations: list[Relation] = []
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if earlier.id != later.id:
            relations.append(Relation(kind="order", op=RelationOp.le,
                                       left=earlier.id, right=later.id))
    return relations


def extract_schema(state: GraphState) -> dict[str, Any]:
    if state.template is None:
        return {"template": None, "field_schema": FieldSchema()}
    tmpl = state.template
    new_relations = list(tmpl.relations) + _date_order_relations(tmpl.fields)
    rebuilt = CanonicalTemplate(
        template_id=tmpl.template_id, doc_type=tmpl.doc_type, language=tmpl.language,
        direction=tmpl.direction, source=tmpl.source, layout_blocks=tmpl.layout_blocks,
        fields=tmpl.fields, relations=new_relations,
    )
    notes = {f.id: f.type.value for f in tmpl.fields}
    return {"template": rebuilt, "field_schema": FieldSchema(notes=notes)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/schema/test_infer.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit (local)**

```bash
mkdir -p tests/schema && touch tests/schema/__init__.py
git add -A && git commit -q -m "feat(schema): F4 relation + note inference node"
```

---

## Task 8: extraction integration test — F1..F4 with a fake provider

Proves the four nodes compose into a valid `CanonicalTemplate` without any network. Uses a scripted fake vision provider that returns fields resembling the real bank form (Document 1).

**Files:**
- Test: `tests/extraction/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`tests/extraction/test_pipeline.py`:
```python
import json

from doc2tests.contracts.enums import FieldType, RelationOp, SourceKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.deid.detect import detect_fields
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMResponse
from doc2tests.schema.infer import extract_schema
from doc2tests.template.build import build_template


class _FakeVision:
    name = "fake-vision"

    def __init__(self, payload):
        self._payload = payload

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("vision only")

    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text=json.dumps(self._payload))


def _apply(state, patch):
    return state.model_copy(update=patch)


def test_full_extraction_chain(tmp_path):
    img = tmp_path / "form.jpeg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    provider = _FakeVision({
        "raw_text": "בקשה להעברת תעודת זכאות",
        "fields": [
            {"label": "מספר זהות (מבקש ראשי)", "value": "123456782", "value_kind": "handwritten"},
            {"label": "תאריך חתימת חוזה", "value": "2019", "value_kind": "handwritten"},
            {"label": "תאריך כניסה לדירה", "value": "31.10.21", "value_kind": "handwritten"},
        ],
    })

    state = GraphState(input_ref=InputRef(path=str(img), kind=SourceKind.image))
    state = _apply(state, ingest_parse(state, provider))
    state = _apply(state, detect_fields(state))
    state = _apply(state, build_template(state))
    state = _apply(state, extract_schema(state))

    tmpl = state.template
    assert tmpl is not None
    ids = [f.id for f in tmpl.fields]
    assert "primary_applicant_id" in ids[0]  # slug from first label
    id_field = next(f for f in tmpl.fields if f.type == FieldType.israeli_id)
    assert id_field.constraints.checksum == "israeli_id"
    order_rels = [r for r in tmpl.relations if r.op == RelationOp.le]
    assert order_rels and {order_rels[0].left, order_rels[0].right} <= set(ids)
    assert state.errors == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/extraction/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: tests.extraction` (missing `__init__`) or assertion if run before earlier tasks.

- [ ] **Step 3: Make it pass**

Create `tests/extraction/__init__.py` (empty). No production code needed — this test composes existing nodes. If `ids[0]` slug assertion fails, inspect the actual slug and adjust the label->slug expectation (the first label "מספר זהות (מבקש ראשי)" is non-ascii, so its slug is `field_<n>`; change the assertion to locate the id field by type instead):

```python
    id_field = next(f for f in tmpl.fields if f.type == FieldType.israeli_id)
    assert id_field.id in ids
```
Replace the `assert "primary_applicant_id" in ids[0]` line with the two lines above (the id-by-type lookup already exists below it; keep a single lookup).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/extraction/test_pipeline.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Full suite + lint + types**

Run:
```bash
uv run pytest
uv run ruff check src tests
uv run mypy
```
Expected: all PASS, ruff clean, mypy clean.

- [ ] **Step 6: Commit (local)**

```bash
mkdir -p tests/extraction && touch tests/extraction/__init__.py
git add -A && git commit -q -m "test(extraction): F1..F4 chain integration with fake provider"
```

---

## Task 9 (optional live check): real OpenAI vision on the fixtures

Runs only when `OPENAI_API_KEY` is set; skipped otherwise so CI/offline stays green.

**Files:**
- Test: `tests/extraction/test_live_openai.py`

- [ ] **Step 1: Write the guarded test**

`tests/extraction/test_live_openai.py`:
```python
import os

import pytest

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.deid.detect import detect_fields
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.openai_provider import OpenAIProvider
from doc2tests.schema.infer import extract_schema
from doc2tests.template.build import build_template

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY"
)


def _apply(state, patch):
    return state.model_copy(update=patch)


@pytest.mark.parametrize("fixture", [
    "tests/fixtures/doc2_printed_tax_letter.jpeg",
    "tests/fixtures/doc1_handwritten_bank_form.jpeg",
])
def test_live_extraction_produces_template(fixture):
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    provider = OpenAIProvider(model=model)
    state = GraphState(input_ref=InputRef(path=fixture, kind=SourceKind.image))
    state = _apply(state, ingest_parse(state, provider))
    state = _apply(state, detect_fields(state))
    state = _apply(state, build_template(state))
    state = _apply(state, extract_schema(state))
    assert state.errors == [], state.errors
    assert state.template is not None
    assert len(state.template.fields) >= 3
```

- [ ] **Step 2: Verify it skips without a key**

Run: `uv run pytest tests/extraction/test_live_openai.py -v`
Expected: SKIPPED (2 skipped) when `OPENAI_API_KEY` is unset.

- [ ] **Step 3: (Manual, when key available) run live**

Run: `OPENAI_API_KEY=sk-... uv run pytest tests/extraction/test_live_openai.py -v`
Expected: PASS on both fixtures, or captured errors to iterate the `VISION_PROMPT`.

- [ ] **Step 4: Commit (local)**

```bash
git add -A && git commit -q -m "test(extraction): guarded live OpenAI vision check on fixtures"
```

---

## Definition of Done (Plan 2)

- [ ] `uv run pytest` green (offline suite; live test skipped without key).
- [ ] `uv run mypy` clean under `strict`.
- [ ] `uv run ruff check src tests` clean.
- [ ] `ingest_parse -> detect_fields -> build_template -> extract_schema` produces a valid `CanonicalTemplate` from a fake provider, with Israeli-ID constraints and a date-order relation.
- [ ] Live OpenAI path exists and is one env var away from running on the two real fixtures.

**Next:** Plan 3 (Generation & Render — F5/X3/F6) consumes the `CanonicalTemplate` this plan produces.

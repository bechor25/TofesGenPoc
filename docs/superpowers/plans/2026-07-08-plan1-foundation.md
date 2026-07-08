# Foundation Implementation Plan (Plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the typed core of doc2tests — the Pydantic contracts (source of truth), the Israeli validators library, and the pluggable LLM/VLM provider layer — all testable in isolation with no external API.

**Architecture:** `contracts/` holds every Pydantic model the pipeline passes around (the canonical template is defined here). `validators/` holds pure-code Israeli correctness checks (ID checksum, dates, gush/helka, phone, branch). `providers/` holds one `LLMProvider` interface with OpenAI + Ollama backends selected per-node via config. Dependency injection keeps every unit offline-testable.

**Tech Stack:** Python 3.12 (pinned via uv), Pydantic v2, `openai` SDK, `requests`, pytest, ruff, mypy.

**Note on git:** Project is local-only. Commits are local checkpoints (no remote, no push) — they enable per-task review and rollback. If you prefer no git at all, replace each "Commit" step with "run full suite + lint green".

---

## File Structure

```
doc2tests/
├── pyproject.toml                     # uv project, deps, ruff+mypy+pytest config
├── .python-version                    # 3.12
├── .env.example                       # OPENAI_API_KEY, OLLAMA_HOST
├── .gitignore
├── src/doc2tests/
│   ├── __init__.py
│   ├── contracts/
│   │   ├── __init__.py                # re-exports
│   │   ├── enums.py                   # FieldType, TestClass, PiiType, ...
│   │   ├── template.py                # BBox, Constraints, Field, Relation, CanonicalTemplate
│   │   ├── records.py                 # Value, Record
│   │   └── state.py                   # InputRef, ParseResult, DetectedField, GraphState, RunConfig, ...
│   ├── validators/
│   │   ├── __init__.py                # registry: validate(type, value)
│   │   ├── israeli_id.py
│   │   ├── dates.py
│   │   ├── gush_helka.py
│   │   └── contact.py                 # phone + bank_branch
│   └── providers/
│       ├── __init__.py
│       ├── base.py                    # LLMProvider Protocol, LLMResponse, model config
│       ├── openai_provider.py
│       ├── ollama_provider.py
│       └── factory.py                 # build provider from config, per-node selection
└── tests/
    ├── contracts/
    ├── validators/
    └── providers/
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.env.example`, `.gitignore`, `src/doc2tests/__init__.py`

- [ ] **Step 1: Init uv project pinned to Python 3.12**

Run:
```bash
cd /Users/bechorsimhaevness/Desktop/code/TofesGenPoc
uv init --lib --name doc2tests --python 3.12 .
```
Expected: creates `pyproject.toml`, `.python-version` (3.12), `src/doc2tests/`. If `uv init` refuses because files exist, create `pyproject.toml` manually per Step 2 and run `uv python pin 3.12`.

- [ ] **Step 2: Overwrite `pyproject.toml`**

```toml
[project]
name = "doc2tests"
version = "0.1.0"
description = "Document -> canonical template -> QA test population -> filled documents"
requires-python = ">=3.12,<3.13"
dependencies = [
    "pydantic>=2.7",
    "python-dotenv>=1.0",
    "openai>=1.40",
    "requests>=2.32",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "ruff>=0.5",
    "mypy>=1.10",
    "types-requests>=2.32",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src", "tests"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 3: Create `.python-version`**

```
3.12
```

- [ ] **Step 4: Create `.env.example`**

```
OPENAI_API_KEY=sk-...
OPENAI_VISION_MODEL=gpt-4o
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

- [ ] **Step 5: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
.mypy_cache/
.pytest_cache/
.ruff_cache/
dist/
```

- [ ] **Step 6: Sync env + create test dirs**

Run:
```bash
uv sync --extra dev
mkdir -p tests/contracts tests/validators tests/providers
touch tests/__init__.py tests/contracts/__init__.py tests/validators/__init__.py tests/providers/__init__.py
```
Expected: `.venv/` created, dev deps installed.

- [ ] **Step 7: Verify toolchain**

Run:
```bash
uv run python -c "import pydantic, openai, requests; print('ok', pydantic.VERSION)"
uv run pytest -q
```
Expected: prints `ok 2.x`; pytest reports "no tests ran" (exit 5 is fine at this stage).

- [ ] **Step 8: Commit (local)**

```bash
git init -q && git add -A && git commit -q -m "chore: scaffold doc2tests (uv, py3.12, tooling)"
```

---

## Task 2: contracts/enums.py

**Files:**
- Create: `src/doc2tests/contracts/enums.py`
- Test: `tests/contracts/test_enums.py`

- [ ] **Step 1: Write the failing test**

`tests/contracts/test_enums.py`:
```python
from doc2tests.contracts.enums import FieldType, TestClass, PiiType, SourceKind, RenderStrategy, RelationOp


def test_field_type_has_semantic_types():
    values = {t.value for t in FieldType}
    assert {"hebrew_name", "israeli_id", "date", "gush_helka", "assessment_number",
            "bank_branch", "address", "phone", "currency", "enum", "free_text"} <= values


def test_test_class_three_members():
    assert [c.value for c in TestClass] == ["equivalence", "boundary", "negative"]


def test_enums_are_str():
    assert FieldType.israeli_id == "israeli_id"
    assert PiiType.IL_ID == "IL_ID"
    assert SourceKind.image == "image"
    assert RenderStrategy.reconstruct == "reconstruct"
    assert RelationOp.le == "<="
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/contracts/test_enums.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc2tests.contracts'`

- [ ] **Step 3: Write minimal implementation**

Create `src/doc2tests/contracts/__init__.py` (empty for now).
Create `src/doc2tests/contracts/enums.py`:
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


class TestClass(StrEnum):
    equivalence = "equivalence"
    boundary = "boundary"
    negative = "negative"


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


class RenderStrategy(StrEnum):
    reconstruct = "reconstruct"
    overlay = "overlay"


class ValueKind(StrEnum):
    printed = "printed"
    handwritten = "handwritten"


class RelationOp(StrEnum):
    le = "<="
    lt = "<"
    ge = ">="
    gt = ">"
    eq = "=="
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/contracts/test_enums.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(contracts): semantic enums"
```

---

## Task 3: contracts/template.py — the canonical template

**Files:**
- Create: `src/doc2tests/contracts/template.py`
- Test: `tests/contracts/test_template.py`

- [ ] **Step 1: Write the failing test**

`tests/contracts/test_template.py`:
```python
import json
from doc2tests.contracts.template import (
    BBox, Constraints, Field, Relation, CanonicalTemplate, DocSource, LayoutBlock,
)
from doc2tests.contracts.enums import (
    FieldType, ValueKind, PiiType, SourceKind, RenderStrategy, RelationOp,
)


def _sample_template() -> CanonicalTemplate:
    return CanonicalTemplate(
        doc_type="bank-eligibility-transfer",
        source=DocSource(kind=SourceKind.image, pages=1, render_strategy=RenderStrategy.reconstruct),
        layout_blocks=[LayoutBlock(id="b1", kind="field", page=1,
                                   bbox=BBox(page=1, x=0.6, y=0.34, w=0.15, h=0.03))],
        fields=[
            Field(
                id="primary_applicant_id",
                label="מספר זהות (מבקש ראשי)",
                type=FieldType.israeli_id,
                value_kind=ValueKind.handwritten,
                pii=True, pii_type=PiiType.IL_ID,
                constraints=Constraints(required=True, checksum="israeli_id", length=9),
                placeholder="{{ primary_applicant_id }}",
                bbox=BBox(page=1, x=0.6, y=0.34, w=0.15, h=0.03),
            ),
            Field(id="entry_date", label="תאריך כניסה", type=FieldType.date,
                  placeholder="{{ entry_date }}"),
            Field(id="contract_date", label="תאריך חוזה", type=FieldType.date,
                  placeholder="{{ contract_date }}"),
        ],
        relations=[Relation(kind="order", op=RelationOp.le,
                            left="contract_date", right="entry_date")],
    )


def test_template_roundtrips_through_json():
    t = _sample_template()
    dumped = t.model_dump_json()
    reloaded = CanonicalTemplate.model_validate_json(dumped)
    assert reloaded == t
    assert json.loads(dumped)["fields"][0]["type"] == "israeli_id"


def test_field_ids_must_be_unique():
    import pytest
    from pydantic import ValidationError
    t = _sample_template()
    data = t.model_dump()
    data["fields"].append(data["fields"][0])  # duplicate id
    with pytest.raises(ValidationError):
        CanonicalTemplate.model_validate(data)


def test_relation_endpoints_must_reference_existing_fields():
    import pytest
    from pydantic import ValidationError
    data = _sample_template().model_dump()
    data["relations"][0]["right"] = "no_such_field"
    with pytest.raises(ValidationError):
        CanonicalTemplate.model_validate(data)


def test_placeholder_defaults_to_field_id():
    f = Field(id="foo", label="Foo", type=FieldType.free_text)
    assert f.placeholder == "{{ foo }}"


def test_bbox_is_optional():
    f = Field(id="x", label="X", type=FieldType.free_text)
    assert f.bbox is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/contracts/test_template.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc2tests.contracts.template'`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/contracts/template.py`:
```python
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field as PField, model_validator

from doc2tests.contracts.enums import (
    FieldType, PiiType, RelationOp, RenderStrategy, SourceKind, ValueKind,
)


class BBox(BaseModel):
    page: int = 1
    x: float
    y: float
    w: float
    h: float


class LayoutBlock(BaseModel):
    id: str
    kind: Literal["heading", "paragraph", "table", "field"]
    page: int = 1
    bbox: BBox | None = None


class Constraints(BaseModel):
    required: bool = False
    checksum: str | None = None          # validator key, e.g. "israeli_id"
    length: int | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    enum_values: list[str] | None = None


class Field(BaseModel):
    id: str
    label: str
    type: FieldType
    value_kind: ValueKind | None = None
    pii: bool = False
    pii_type: PiiType | None = None
    constraints: Constraints = PField(default_factory=Constraints)
    placeholder: str = ""
    bbox: BBox | None = None

    @model_validator(mode="after")
    def _default_placeholder(self) -> Field:
        if not self.placeholder:
            object.__setattr__(self, "placeholder", f"{{{{ {self.id} }}}}")
        return self


class Relation(BaseModel):
    kind: Literal["order", "derived"]
    op: RelationOp | None = None
    left: str | None = None
    right: str | None = None
    field: str | None = None
    from_fields: list[str] = PField(default_factory=list, alias="from")

    model_config = {"populate_by_name": True}


class DocSource(BaseModel):
    kind: SourceKind
    pages: int = 1
    render_strategy: RenderStrategy = RenderStrategy.reconstruct


class CanonicalTemplate(BaseModel):
    template_id: str = PField(default_factory=lambda: str(uuid.uuid4()))
    doc_type: str
    language: str = "he"
    direction: str = "rtl"
    source: DocSource
    layout_blocks: list[LayoutBlock] = PField(default_factory=list)
    fields: list[Field] = PField(default_factory=list)
    relations: list[Relation] = PField(default_factory=list)

    @model_validator(mode="after")
    def _check_integrity(self) -> CanonicalTemplate:
        ids = [f.id for f in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("field ids must be unique")
        idset = set(ids)
        for r in self.relations:
            for endpoint in (r.left, r.right, r.field, *r.from_fields):
                if endpoint is not None and endpoint not in idset:
                    raise ValueError(f"relation references unknown field: {endpoint}")
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/contracts/test_template.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run mypy + ruff**

Run: `uv run ruff check src tests && uv run mypy src/doc2tests/contracts`
Expected: no errors.

- [ ] **Step 6: Commit (local)**

```bash
git add -A && git commit -q -m "feat(contracts): canonical template models + integrity checks"
```

---

## Task 4: contracts/records.py + contracts/state.py — pipeline types

**Files:**
- Create: `src/doc2tests/contracts/records.py`, `src/doc2tests/contracts/state.py`
- Modify: `src/doc2tests/contracts/__init__.py`
- Test: `tests/contracts/test_state.py`

- [ ] **Step 1: Write the failing test**

`tests/contracts/test_state.py`:
```python
from doc2tests.contracts.records import Value, Record
from doc2tests.contracts.state import (
    InputRef, RunConfig, GraphState, StageError,
)
from doc2tests.contracts.enums import TestClass, SourceKind


def test_record_carries_class_and_validity():
    rec = Record(
        index=0,
        test_class=TestClass.negative,
        expected_valid=False,
        violates="israeli_id.checksum",
        values={"primary_applicant_id": Value(field_id="primary_applicant_id",
                                              value="123456789", valid=False)},
    )
    assert rec.expected_valid is False
    assert rec.values["primary_applicant_id"].value == "123456789"


def test_runconfig_defaults():
    cfg = RunConfig()
    assert cfg.n == 100
    assert abs(cfg.mix[TestClass.equivalence] + cfg.mix[TestClass.boundary]
               + cfg.mix[TestClass.negative] - 1.0) < 1e-9
    assert cfg.formats == ["html", "docx"]


def test_graphstate_minimal_construction():
    st = GraphState(
        input_ref=InputRef(path="tests/fixtures/doc2.jpeg", kind=SourceKind.image),
        config=RunConfig(n=10),
    )
    assert st.population == []
    assert st.errors == []
    assert st.template is None


def test_stage_error_records_stage():
    e = StageError(stage="ingest_parse", message="vision timeout")
    assert e.stage == "ingest_parse"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/contracts/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc2tests.contracts.records'`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/contracts/records.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, Field as PField

from doc2tests.contracts.enums import TestClass


class Value(BaseModel):
    field_id: str
    value: str
    valid: bool = True


class Record(BaseModel):
    index: int
    test_class: TestClass
    expected_valid: bool
    violates: str | None = None          # rule key when expected_valid is False
    values: dict[str, Value] = PField(default_factory=dict)
```

`src/doc2tests/contracts/state.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, Field as PField

from doc2tests.contracts.enums import FieldType, PiiType, SourceKind, TestClass, ValueKind
from doc2tests.contracts.records import Record
from doc2tests.contracts.template import BBox, CanonicalTemplate


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


class DetectedField(BaseModel):
    label: str
    value: str
    type: FieldType = FieldType.free_text
    pii: bool = False
    pii_type: PiiType | None = None
    value_kind: ValueKind = ValueKind.printed
    bbox: BBox | None = None


class FieldSchema(BaseModel):
    # per-field inferred constraints keyed by field id; relations live on the template
    notes: dict[str, str] = PField(default_factory=dict)


class ReviewDecision(BaseModel):
    approved: bool
    edits: dict[str, str] = PField(default_factory=dict)


class CoverageCell(BaseModel):
    field_id: str
    test_class: TestClass
    count: int


class CoverageReport(BaseModel):
    cells: list[CoverageCell] = PField(default_factory=list)
    rules_exercised: list[str] = PField(default_factory=list)
    gaps: list[str] = PField(default_factory=list)


class RenderedDoc(BaseModel):
    record_index: int
    fmt: str
    path: str


class StageError(BaseModel):
    stage: str
    message: str


class RunConfig(BaseModel):
    n: int = 100
    mix: dict[TestClass, float] = PField(
        default_factory=lambda: {
            TestClass.equivalence: 0.6,
            TestClass.boundary: 0.25,
            TestClass.negative: 0.15,
        }
    )
    formats: list[str] = PField(default_factory=lambda: ["html", "docx"])
    seed: int = 42


class GraphState(BaseModel):
    input_ref: InputRef
    config: RunConfig = PField(default_factory=RunConfig)
    parse_result: ParseResult | None = None
    detected_fields: list[DetectedField] = PField(default_factory=list)
    template: CanonicalTemplate | None = None
    schema_: FieldSchema | None = PField(default=None, alias="schema")
    review: ReviewDecision | None = None
    population: list[Record] = PField(default_factory=list)
    coverage: CoverageReport | None = None
    outputs: list[RenderedDoc] = PField(default_factory=list)
    errors: list[StageError] = PField(default_factory=list)

    model_config = {"populate_by_name": True}
```

Modify `src/doc2tests/contracts/__init__.py`:
```python
from doc2tests.contracts.enums import (
    FieldType, PiiType, RelationOp, RenderStrategy, SourceKind, TestClass, ValueKind,
)
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import (
    CoverageReport, DetectedField, FieldSchema, GraphState, InputRef, ParsedField,
    ParseResult, RenderedDoc, ReviewDecision, RunConfig, StageError,
)
from doc2tests.contracts.template import (
    BBox, CanonicalTemplate, Constraints, DocSource, Field, LayoutBlock, Relation,
)

__all__ = [
    "FieldType", "PiiType", "RelationOp", "RenderStrategy", "SourceKind", "TestClass",
    "ValueKind", "Record", "Value", "CoverageReport", "DetectedField", "FieldSchema",
    "GraphState", "InputRef", "ParsedField", "ParseResult", "RenderedDoc",
    "ReviewDecision", "RunConfig", "StageError", "BBox", "CanonicalTemplate",
    "Constraints", "DocSource", "Field", "LayoutBlock", "Relation",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/contracts/ -v`
Expected: PASS (all contracts tests)

- [ ] **Step 5: Run mypy + ruff**

Run: `uv run ruff check src tests && uv run mypy src`
Expected: no errors. (Note: `schema_` uses alias `schema` to avoid shadowing Pydantic's method.)

- [ ] **Step 6: Commit (local)**

```bash
git add -A && git commit -q -m "feat(contracts): pipeline state, records, run config"
```

---

## Task 5: validators/israeli_id.py — ID checksum (TDD)

Algorithm: 9 digits; weight each digit by 1,2,1,2,1,2,1,2,1; if a product > 9 subtract 9; sum; valid iff `sum % 10 == 0`.

**Files:**
- Create: `src/doc2tests/validators/israeli_id.py`, `src/doc2tests/validators/__init__.py`
- Test: `tests/validators/test_israeli_id.py`

- [ ] **Step 1: Write the failing test**

`tests/validators/test_israeli_id.py`:
```python
from doc2tests.validators.israeli_id import is_valid_israeli_id, complete_israeli_id


def test_known_valid_id():
    assert is_valid_israeli_id("123456782") is True


def test_known_invalid_checksum():
    assert is_valid_israeli_id("123456789") is False


def test_pads_short_ids_with_leading_zeros():
    # 8-digit input is zero-padded to 9 before checking
    assert is_valid_israeli_id("00000001") == is_valid_israeli_id("000000001")


def test_rejects_non_digits():
    assert is_valid_israeli_id("12345678X") is False
    assert is_valid_israeli_id("") is False


def test_rejects_too_long():
    assert is_valid_israeli_id("1234567890") is False


def test_complete_produces_valid_id():
    full = complete_israeli_id("12345678")   # 8 digits -> add check digit
    assert len(full) == 9
    assert is_valid_israeli_id(full) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/validators/test_israeli_id.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/validators/__init__.py` (empty for now).
`src/doc2tests/validators/israeli_id.py`:
```python
from __future__ import annotations


def _checksum_total(digits9: str) -> int:
    total = 0
    for i, ch in enumerate(digits9):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n if n < 10 else n - 9
    return total


def is_valid_israeli_id(value: str) -> bool:
    s = value.strip()
    if not s.isdigit() or len(s) > 9:
        return False
    s = s.zfill(9)
    return _checksum_total(s) % 10 == 0


def complete_israeli_id(prefix8: str) -> str:
    if not prefix8.isdigit() or len(prefix8) > 8:
        raise ValueError("prefix must be up to 8 digits")
    base = prefix8.zfill(8) + "0"
    remainder = _checksum_total(base) % 10
    check = (10 - remainder) % 10
    return prefix8.zfill(8) + str(check)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/validators/test_israeli_id.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(validators): israeli id checksum + generator"
```

---

## Task 6: validators/dates.py (TDD)

**Files:**
- Create: `src/doc2tests/validators/dates.py`
- Test: `tests/validators/test_dates.py`

- [ ] **Step 1: Write the failing test**

`tests/validators/test_dates.py`:
```python
from datetime import date
from doc2tests.validators.dates import parse_il_date, is_valid_il_date


def test_parses_dotted_format():
    assert parse_il_date("31.10.21") == date(2021, 10, 31)


def test_parses_slashed_four_digit_year():
    assert parse_il_date("28/07/2019") == date(2019, 7, 28)


def test_parses_year_only():
    assert parse_il_date("2019") == date(2019, 1, 1)


def test_rejects_impossible_date():
    assert parse_il_date("31.02.21") is None
    assert is_valid_il_date("31.02.21") is False


def test_valid_true_for_real_date():
    assert is_valid_il_date("31.10.21") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/validators/test_dates.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/validators/dates.py`:
```python
from __future__ import annotations

from datetime import date


def parse_il_date(value: str) -> date | None:
    s = value.strip()
    for sep in (".", "/", "-"):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3:
                d, m, y = parts
                return _build(d, m, y)
            return None
    if s.isdigit() and len(s) == 4:
        try:
            return date(int(s), 1, 1)
        except ValueError:
            return None
    return None


def _build(d: str, m: str, y: str) -> date | None:
    if not (d.isdigit() and m.isdigit() and y.isdigit()):
        return None
    year = int(y)
    if year < 100:                     # two-digit year -> 2000s
        year += 2000
    try:
        return date(year, int(m), int(d))
    except ValueError:
        return None


def is_valid_il_date(value: str) -> bool:
    return parse_il_date(value) is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/validators/test_dates.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(validators): israeli date parsing"
```

---

## Task 7: validators/gush_helka.py (TDD)

Israeli land registry: גוש (block) 3-6 digits, חלקה (parcel) 1-4 digits, תת-חלקה (sub-parcel) optional 1-4 digits. Canonical string form: `GUSH-HELKA[-SUB]`.

**Files:**
- Create: `src/doc2tests/validators/gush_helka.py`
- Test: `tests/validators/test_gush_helka.py`

- [ ] **Step 1: Write the failing test**

`tests/validators/test_gush_helka.py`:
```python
from doc2tests.validators.gush_helka import is_valid_gush_helka, normalize_gush_helka


def test_valid_full():
    assert is_valid_gush_helka("9007-12-0") is True


def test_valid_without_sub():
    assert is_valid_gush_helka("9007-12") is True


def test_normalizes_leading_zeros_and_spaces():
    assert normalize_gush_helka("009007 / 0012 / 000") == "9007-12-0"


def test_rejects_missing_helka():
    assert is_valid_gush_helka("9007") is False


def test_rejects_non_numeric():
    assert is_valid_gush_helka("gush-12") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/validators/test_gush_helka.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/validators/gush_helka.py`:
```python
from __future__ import annotations

import re

_PARTS = re.compile(r"\d+")


def _tokens(value: str) -> list[str]:
    return _PARTS.findall(value.strip())


def is_valid_gush_helka(value: str) -> bool:
    parts = _tokens(value)
    if len(parts) < 2 or len(parts) > 3:
        return False
    gush, helka = parts[0], parts[1]
    # tokens are numeric by construction (regex \d+); enforce length bounds
    return 1 <= len(gush) <= 6 and 1 <= len(helka) <= 4


def normalize_gush_helka(value: str) -> str:
    parts = _tokens(value)
    if len(parts) < 2:
        raise ValueError("gush/helka requires at least two numeric parts")
    stripped = [str(int(p)) for p in parts[:3]]
    return "-".join(stripped)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/validators/test_gush_helka.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(validators): gush/helka validation + normalization"
```

---

## Task 8: validators/contact.py + registry (TDD)

**Files:**
- Create: `src/doc2tests/validators/contact.py`
- Modify: `src/doc2tests/validators/__init__.py` (add dispatch registry)
- Test: `tests/validators/test_contact.py`, `tests/validators/test_registry.py`

- [ ] **Step 1: Write the failing tests**

`tests/validators/test_contact.py`:
```python
from doc2tests.validators.contact import is_valid_il_phone, is_valid_bank_branch


def test_valid_mobile():
    assert is_valid_il_phone("0521234567") is True


def test_valid_landline_with_dash():
    assert is_valid_il_phone("04-6327888") is True


def test_rejects_wrong_length():
    assert is_valid_il_phone("12345") is False


def test_bank_branch_three_digits():
    assert is_valid_bank_branch("622") is True
    assert is_valid_bank_branch("420") is True


def test_bank_branch_rejects_non_numeric():
    assert is_valid_bank_branch("12X") is False
```

`tests/validators/test_registry.py`:
```python
from doc2tests.validators import validate
from doc2tests.contracts.enums import FieldType


def test_registry_dispatches_israeli_id():
    assert validate(FieldType.israeli_id, "123456782") is True
    assert validate(FieldType.israeli_id, "123456789") is False


def test_registry_dispatches_date():
    assert validate(FieldType.date, "31.10.21") is True


def test_unknown_type_is_permissive():
    # free_text always valid
    assert validate(FieldType.free_text, "anything") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/validators/test_contact.py tests/validators/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError: cannot import name 'validate'`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/validators/contact.py`:
```python
from __future__ import annotations

import re

_DIGITS = re.compile(r"\D")


def _only_digits(value: str) -> str:
    return _DIGITS.sub("", value)


def is_valid_il_phone(value: str) -> bool:
    d = _only_digits(value)
    # Israeli numbers: 9 (landline) or 10 (mobile) digits, leading 0
    return d.startswith("0") and len(d) in (9, 10)


def is_valid_bank_branch(value: str) -> bool:
    d = value.strip()
    return d.isdigit() and 1 <= len(d) <= 3
```

Modify `src/doc2tests/validators/__init__.py`:
```python
from __future__ import annotations

from collections.abc import Callable

from doc2tests.contracts.enums import FieldType
from doc2tests.validators.contact import is_valid_bank_branch, is_valid_il_phone
from doc2tests.validators.dates import is_valid_il_date
from doc2tests.validators.gush_helka import is_valid_gush_helka
from doc2tests.validators.israeli_id import is_valid_israeli_id

_REGISTRY: dict[FieldType, Callable[[str], bool]] = {
    FieldType.israeli_id: is_valid_israeli_id,
    FieldType.date: is_valid_il_date,
    FieldType.gush_helka: is_valid_gush_helka,
    FieldType.phone: is_valid_il_phone,
    FieldType.bank_branch: is_valid_bank_branch,
}


def validate(field_type: FieldType, value: str) -> bool:
    checker = _REGISTRY.get(field_type)
    return True if checker is None else checker(value)


__all__ = [
    "validate", "is_valid_israeli_id", "is_valid_il_date",
    "is_valid_gush_helka", "is_valid_il_phone", "is_valid_bank_branch",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/validators/ -v`
Expected: PASS (all validator tests)

- [ ] **Step 5: Run mypy + ruff**

Run: `uv run ruff check src tests && uv run mypy src`
Expected: no errors.

- [ ] **Step 6: Commit (local)**

```bash
git add -A && git commit -q -m "feat(validators): phone, bank branch, dispatch registry"
```

---

## Task 9: providers/base.py — LLMProvider interface

**Files:**
- Create: `src/doc2tests/providers/base.py`, `src/doc2tests/providers/__init__.py`
- Test: `tests/providers/test_base.py`

- [ ] **Step 1: Write the failing test**

`tests/providers/test_base.py`:
```python
from doc2tests.providers.base import LLMResponse, ProviderSpec, NodeModelConfig


def test_llm_response_holds_text_and_raw():
    r = LLMResponse(text='{"a": 1}', raw={"model": "x"})
    assert r.text == '{"a": 1}'
    assert r.raw["model"] == "x"


def test_node_config_maps_nodes_to_specs():
    cfg = NodeModelConfig(
        default=ProviderSpec(backend="openai", model="gpt-4o"),
        overrides={"generate_population": ProviderSpec(backend="ollama", model="qwen2.5:7b")},
    )
    assert cfg.for_node("ingest_parse").backend == "openai"
    assert cfg.for_node("generate_population").backend == "ollama"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/providers/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/providers/__init__.py` (empty for now).
`src/doc2tests/providers/base.py`:
```python
from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field as PField


class LLMResponse(BaseModel):
    text: str
    raw: dict[str, Any] = PField(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete_text(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> LLMResponse: ...

    def extract_vision(
        self, images: list[bytes], prompt: str, *, json_mode: bool = False
    ) -> LLMResponse: ...


class ProviderSpec(BaseModel):
    backend: Literal["openai", "ollama"]
    model: str


class NodeModelConfig(BaseModel):
    default: ProviderSpec
    overrides: dict[str, ProviderSpec] = PField(default_factory=dict)

    def for_node(self, node: str) -> ProviderSpec:
        return self.overrides.get(node, self.default)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/providers/test_base.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(providers): LLMProvider protocol + per-node config"
```

---

## Task 10: providers/openai_provider.py (TDD with injected client)

**Files:**
- Create: `src/doc2tests/providers/openai_provider.py`
- Test: `tests/providers/test_openai_provider.py`

- [ ] **Step 1: Write the failing test**

`tests/providers/test_openai_provider.py`:
```python
from doc2tests.providers.openai_provider import OpenAIProvider


class _FakeCompletions:
    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)

        class _Msg:
            content = '{"ok": true}'

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

            def model_dump(self):
                return {"model": kwargs["model"]}

        return _Resp()


class _FakeChat:
    def __init__(self, recorder):
        self.completions = _FakeCompletions(recorder)


class _FakeClient:
    def __init__(self, recorder):
        self.chat = _FakeChat(recorder)


def test_complete_text_returns_content():
    rec: dict = {}
    p = OpenAIProvider(model="gpt-4o", client=_FakeClient(rec))
    resp = p.complete_text("hello", system="be brief")
    assert resp.text == '{"ok": true}'
    assert rec["model"] == "gpt-4o"
    assert rec["messages"][0]["role"] == "system"


def test_extract_vision_embeds_image_as_data_uri():
    rec: dict = {}
    p = OpenAIProvider(model="gpt-4o", client=_FakeClient(rec))
    p.extract_vision([b"\xff\xd8\xff"], "read this", json_mode=True)
    content = rec["messages"][-1]["content"]
    image_parts = [c for c in content if c["type"] == "image_url"]
    assert image_parts and image_parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert rec["response_format"] == {"type": "json_object"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/providers/test_openai_provider.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/providers/openai_provider.py`:
```python
from __future__ import annotations

import base64
from typing import Any

from doc2tests.providers.base import LLMResponse


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, client: Any | None = None, api_key: str | None = None):
        self.model = model
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)

    def _create(self, messages: list[dict[str, Any]], json_mode: bool) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        raw = resp.model_dump() if hasattr(resp, "model_dump") else {}
        return LLMResponse(text=text, raw=raw)

    def complete_text(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> LLMResponse:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._create(messages, json_mode)

    def extract_vision(
        self, images: list[bytes], prompt: str, *, json_mode: bool = False
    ) -> LLMResponse:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            b64 = base64.b64encode(img).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        return self._create([{"role": "user", "content": content}], json_mode)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/providers/test_openai_provider.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(providers): openai backend (text + vision)"
```

---

## Task 11: providers/ollama_provider.py (TDD with injected session)

**Files:**
- Create: `src/doc2tests/providers/ollama_provider.py`
- Test: `tests/providers/test_ollama_provider.py`

- [ ] **Step 1: Write the failing test**

`tests/providers/test_ollama_provider.py`:
```python
from doc2tests.providers.ollama_provider import OllamaProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.last_url = None
        self.last_json = None

    def post(self, url, json, timeout):
        self.last_url = url
        self.last_json = json
        return _FakeResponse(self._payload)


def test_complete_text_hits_generate_endpoint():
    sess = _FakeSession({"response": "shalom"})
    p = OllamaProvider(model="qwen2.5:7b", host="http://localhost:11434", session=sess)
    resp = p.complete_text("hi", json_mode=True)
    assert resp.text == "shalom"
    assert sess.last_url.endswith("/api/generate")
    assert sess.last_json["model"] == "qwen2.5:7b"
    assert sess.last_json["format"] == "json"
    assert sess.last_json["stream"] is False


def test_extract_vision_passes_base64_images():
    sess = _FakeSession({"response": "{}"})
    p = OllamaProvider(model="llava", host="http://localhost:11434", session=sess)
    p.extract_vision([b"\xff\xd8\xff"], "read")
    assert isinstance(sess.last_json["images"], list) and sess.last_json["images"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/providers/test_ollama_provider.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/providers/ollama_provider.py`:
```python
from __future__ import annotations

import base64
from typing import Any

from doc2tests.providers.base import LLMResponse


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        session: Any | None = None,
        timeout: int = 120,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        if session is not None:
            self._session = session
        else:
            import requests

            self._session = requests.Session()

    def _generate(self, payload: dict[str, Any]) -> LLMResponse:
        payload = {"model": self.model, "stream": False, **payload}
        resp = self._session.post(
            f"{self.host}/api/generate", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(text=data.get("response", ""), raw=data)

    def complete_text(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> LLMResponse:
        payload: dict[str, Any] = {"prompt": prompt}
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        return self._generate(payload)

    def extract_vision(
        self, images: list[bytes], prompt: str, *, json_mode: bool = False
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "images": [base64.b64encode(img).decode("ascii") for img in images],
        }
        if json_mode:
            payload["format"] = "json"
        return self._generate(payload)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/providers/test_ollama_provider.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(providers): ollama backend (text + vision)"
```

---

## Task 12: providers/factory.py — build provider from spec + per-node selection

**Files:**
- Create: `src/doc2tests/providers/factory.py`
- Modify: `src/doc2tests/providers/__init__.py` (re-exports)
- Test: `tests/providers/test_factory.py`

- [ ] **Step 1: Write the failing test**

`tests/providers/test_factory.py`:
```python
from doc2tests.providers.factory import build_provider, provider_for_node
from doc2tests.providers.base import ProviderSpec, NodeModelConfig
from doc2tests.providers.openai_provider import OpenAIProvider
from doc2tests.providers.ollama_provider import OllamaProvider


def test_build_openai_without_calling_network():
    p = build_provider(ProviderSpec(backend="openai", model="gpt-4o"),
                       openai_client=object())
    assert isinstance(p, OpenAIProvider)
    assert p.model == "gpt-4o"


def test_build_ollama():
    p = build_provider(ProviderSpec(backend="ollama", model="qwen2.5:7b"),
                       ollama_session=object())
    assert isinstance(p, OllamaProvider)


def test_provider_for_node_uses_override():
    cfg = NodeModelConfig(
        default=ProviderSpec(backend="openai", model="gpt-4o"),
        overrides={"generate_population": ProviderSpec(backend="ollama", model="qwen2.5:7b")},
    )
    p = provider_for_node("generate_population", cfg,
                          openai_client=object(), ollama_session=object())
    assert isinstance(p, OllamaProvider)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/providers/test_factory.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`src/doc2tests/providers/factory.py`:
```python
from __future__ import annotations

from typing import Any

from doc2tests.providers.base import LLMProvider, NodeModelConfig, ProviderSpec
from doc2tests.providers.ollama_provider import OllamaProvider
from doc2tests.providers.openai_provider import OpenAIProvider


def build_provider(
    spec: ProviderSpec,
    *,
    openai_client: Any | None = None,
    ollama_session: Any | None = None,
    openai_api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
) -> LLMProvider:
    if spec.backend == "openai":
        return OpenAIProvider(model=spec.model, client=openai_client, api_key=openai_api_key)
    if spec.backend == "ollama":
        return OllamaProvider(model=spec.model, host=ollama_host, session=ollama_session)
    raise ValueError(f"unknown backend: {spec.backend}")


def provider_for_node(
    node: str,
    config: NodeModelConfig,
    *,
    openai_client: Any | None = None,
    ollama_session: Any | None = None,
    openai_api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
) -> LLMProvider:
    return build_provider(
        config.for_node(node),
        openai_client=openai_client,
        ollama_session=ollama_session,
        openai_api_key=openai_api_key,
        ollama_host=ollama_host,
    )
```

Modify `src/doc2tests/providers/__init__.py`:
```python
from doc2tests.providers.base import (
    LLMProvider, LLMResponse, NodeModelConfig, ProviderSpec,
)
from doc2tests.providers.factory import build_provider, provider_for_node
from doc2tests.providers.ollama_provider import OllamaProvider
from doc2tests.providers.openai_provider import OpenAIProvider

__all__ = [
    "LLMProvider", "LLMResponse", "NodeModelConfig", "ProviderSpec",
    "build_provider", "provider_for_node", "OllamaProvider", "OpenAIProvider",
]
```

- [ ] **Step 4: Run full suite + lint + types**

Run:
```bash
uv run pytest -v
uv run ruff check src tests
uv run mypy src
```
Expected: all tests PASS, ruff clean, mypy clean.

- [ ] **Step 5: Commit (local)**

```bash
git add -A && git commit -q -m "feat(providers): factory + per-node provider selection"
```

---

## Definition of Done (Plan 1)

- [ ] `uv run pytest` green (contracts + validators + providers).
- [ ] `uv run mypy src` clean under `strict`.
- [ ] `uv run ruff check src tests` clean.
- [ ] `contracts/` exports the full canonical-template + pipeline-state model set.
- [ ] `validators.validate(FieldType, value)` dispatches all Israeli validators.
- [ ] `providers.provider_for_node(node, config)` returns an OpenAI or Ollama backend per config, constructible without network in tests.

**Next:** Plan 2 (Extraction — F1/F2/F3/F4) consumes `contracts` + `providers`; Plan 3 (Generation & Render — F5/X3/F6) consumes `contracts` + `validators`; Plan 4 (Orchestration & UI — F7).

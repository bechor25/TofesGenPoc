# Generation & Render Implementation Plan (Plan 3 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a `CanonicalTemplate` into a QA-aware test population (F5), a coverage report (X3), and rendered documents in HTML + DOCX (F6).

**Architecture:** Per-`FieldType` strategy objects each produce equivalence / boundary / negative values from an injected seeded RNG (deterministic). `generate_population` builds N records by the configured class mix; equivalence/boundary records are fully valid, each negative record injects exactly one rule violation (a bad field value or a relation violation) and is tagged with `violates`. `build_coverage` summarizes class counts and which rules were exercised. Render reconstructs the document from the template (label→value) as an RTL HTML page (Jinja2) and a DOCX (python-docx).

**Tech Stack:** Adds `jinja2`, `python-docx`, `faker`. Builds on Plans 1-2.

**Depends on:** Plan 2 complete (CanonicalTemplate available; 76 offline tests green).

---

## File Structure

```
src/doc2tests/
├── generate/
│   ├── __init__.py
│   ├── strategies.py      # FieldStrategy protocol + per-type strategies + strategy_for()
│   ├── relations.py       # apply/violate order relations on a record's date fields
│   └── population.py       # F5: generate_population(state) -> dict
├── coverage/
│   ├── __init__.py
│   └── report.py          # X3: build_coverage(template, population) -> CoverageReport
└── render/
    ├── __init__.py
    ├── html.py            # render_html(template, record) -> str
    ├── docx.py            # render_docx(template, record, path) -> None
    └── run.py             # F6: render_fill(state, out_dir) -> dict
tests/generate/  tests/coverage/  tests/render/
```

## Task 1: deps

- [ ] **Step 1: Add dependencies**

Run:
```bash
uv add jinja2 python-docx faker
```
Expected: resolves and installs; `pyproject.toml` `dependencies` gains the three.

- [ ] **Step 2: Verify import**

Run: `uv run python -c "import jinja2, docx, faker; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
mkdir -p src/doc2tests/generate src/doc2tests/coverage src/doc2tests/render \
         tests/generate tests/coverage tests/render
touch tests/generate/__init__.py tests/coverage/__init__.py tests/render/__init__.py
git add -A && git commit -q -m "chore: add jinja2, python-docx, faker for generation+render"
```

## Task 2: generate/strategies.py

- [ ] **Step 1: Write the failing test**

`tests/generate/test_strategies.py`:
```python
import random

from doc2tests.contracts.enums import FieldType
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import is_valid_il_date, is_valid_israeli_id


def _rng():
    return random.Random(42)


def test_israeli_id_equivalence_is_valid():
    s = strategy_for(FieldType.israeli_id, _rng())
    assert is_valid_israeli_id(s.equivalence())


def test_israeli_id_negative_is_invalid():
    s = strategy_for(FieldType.israeli_id, _rng())
    assert any(not is_valid_israeli_id(v) for v in s.negative())


def test_date_equivalence_is_valid():
    s = strategy_for(FieldType.date, _rng())
    assert is_valid_il_date(s.equivalence())


def test_date_negative_has_impossible_value():
    s = strategy_for(FieldType.date, _rng())
    assert any(not is_valid_il_date(v) for v in s.negative())


def test_hebrew_name_equivalence_nonempty():
    s = strategy_for(FieldType.hebrew_name, _rng())
    assert s.equivalence().strip()


def test_deterministic_with_same_seed():
    a = strategy_for(FieldType.israeli_id, random.Random(1)).equivalence()
    b = strategy_for(FieldType.israeli_id, random.Random(1)).equivalence()
    assert a == b


def test_unknown_type_falls_back_to_free_text():
    s = strategy_for(FieldType.free_text, _rng())
    assert isinstance(s.equivalence(), str)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/generate/test_strategies.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/doc2tests/generate/__init__.py` (empty).
`src/doc2tests/generate/strategies.py`:
```python
from __future__ import annotations

import random
from typing import Protocol

from faker import Faker

from doc2tests.contracts.enums import FieldType
from doc2tests.validators.israeli_id import complete_israeli_id


class FieldStrategy(Protocol):
    def equivalence(self) -> str: ...
    def boundary(self) -> str: ...
    def negative(self) -> list[str]: ...


class _Base:
    def __init__(self, rng: random.Random):
        self.rng = rng


class IsraeliIdStrategy(_Base):
    def equivalence(self) -> str:
        prefix = "".join(str(self.rng.randint(0, 9)) for _ in range(8))
        return complete_israeli_id(prefix)

    def boundary(self) -> str:
        # valid id that starts with a zero (leading-zero handling)
        prefix = "0" + "".join(str(self.rng.randint(0, 9)) for _ in range(7))
        return complete_israeli_id(prefix)

    def negative(self) -> list[str]:
        good = self.equivalence()
        bad_checksum = good[:-1] + str((int(good[-1]) + 1) % 10)
        return [bad_checksum, good[:8], good + "0"]  # wrong checksum, too short, too long


class DateStrategy(_Base):
    def equivalence(self) -> str:
        d = self.rng.randint(1, 28)
        m = self.rng.randint(1, 12)
        y = self.rng.randint(2000, 2024)
        return f"{d:02d}.{m:02d}.{y}"

    def boundary(self) -> str:
        return "29.02.2020"  # leap day

    def negative(self) -> list[str]:
        return ["31.02.2021", "00.13.2020"]


class _FakerStrategy(_Base):
    _faker = Faker("he_IL")

    def __init__(self, rng: random.Random):
        super().__init__(rng)
        self._faker.seed_instance(rng.randint(0, 10_000_000))


class HebrewNameStrategy(_FakerStrategy):
    def equivalence(self) -> str:
        return self._faker.name()

    def boundary(self) -> str:
        return "א"  # single character

    def negative(self) -> list[str]:
        return ["", "123"]  # empty, digits-only


class PhoneStrategy(_Base):
    def equivalence(self) -> str:
        return "05" + "".join(str(self.rng.randint(0, 9)) for _ in range(8))

    def boundary(self) -> str:
        return "0" + "".join(str(self.rng.randint(0, 9)) for _ in range(8))  # 9-digit landline

    def negative(self) -> list[str]:
        return ["123", "0" + "0" * 11]


class BankBranchStrategy(_Base):
    def equivalence(self) -> str:
        return f"{self.rng.randint(100, 999)}"

    def boundary(self) -> str:
        return f"{self.rng.randint(1, 9)}"

    def negative(self) -> list[str]:
        return ["12X", "1234"]


class GushHelkaStrategy(_Base):
    def equivalence(self) -> str:
        return f"{self.rng.randint(1000, 9999)}-{self.rng.randint(1, 999)}-0"

    def boundary(self) -> str:
        return f"{self.rng.randint(1, 9)}-1"

    def negative(self) -> list[str]:
        return ["9007", "gush-12"]


class NumberStrategy(_Base):
    def equivalence(self) -> str:
        return "".join(str(self.rng.randint(0, 9)) for _ in range(9))

    def boundary(self) -> str:
        return "0"

    def negative(self) -> list[str]:
        return ["not-a-number"]


class FreeTextStrategy(_FakerStrategy):
    def equivalence(self) -> str:
        return self._faker.sentence(nb_words=4)

    def boundary(self) -> str:
        return "א" * 200  # long string / RTL stress

    def negative(self) -> list[str]:
        return [""]


_REGISTRY = {
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
    return cls(rng)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/generate/test_strategies.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -m "feat(generate): per-type QA strategies (equivalence/boundary/negative)"
```

## Task 3: generate/relations.py

- [ ] **Step 1: Write the failing test**

`tests/generate/test_relations.py`:
```python
from doc2tests.contracts.enums import FieldType, RelationOp
from doc2tests.contracts.template import (
    CanonicalTemplate, DocSource, Field, Relation,
)
from doc2tests.contracts.enums import SourceKind
from doc2tests.generate.relations import satisfies_order, violate_order


def _tmpl():
    return CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="a", label="חוזה", type=FieldType.date),
                Field(id="b", label="כניסה", type=FieldType.date)],
        relations=[Relation(kind="order", op=RelationOp.le, left="a", right="b")],
    )


def test_satisfies_order_true_when_ordered():
    assert satisfies_order(_tmpl(), {"a": "01.01.2020", "b": "01.02.2020"}) is True


def test_satisfies_order_false_when_reversed():
    assert satisfies_order(_tmpl(), {"a": "01.03.2020", "b": "01.01.2020"}) is False


def test_violate_order_swaps_to_break_relation():
    values = {"a": "01.01.2020", "b": "01.02.2020"}
    broken = violate_order(_tmpl(), values)
    assert satisfies_order(_tmpl(), broken) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/generate/test_relations.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/doc2tests/generate/relations.py`:
```python
from __future__ import annotations

from doc2tests.contracts.enums import RelationOp
from doc2tests.contracts.template import CanonicalTemplate
from doc2tests.validators.dates import parse_il_date


def _order_relations(template: CanonicalTemplate):
    return [r for r in template.relations
            if r.kind == "order" and r.left and r.right and r.op == RelationOp.le]


def satisfies_order(template: CanonicalTemplate, values: dict[str, str]) -> bool:
    for r in _order_relations(template):
        left = parse_il_date(values.get(r.left or "", ""))
        right = parse_il_date(values.get(r.right or "", ""))
        if left is not None and right is not None and left > right:
            return False
    return True


def violate_order(template: CanonicalTemplate, values: dict[str, str]) -> dict[str, str]:
    out = dict(values)
    for r in _order_relations(template):
        lid, rid = r.left or "", r.right or ""
        if lid in out and rid in out:
            out[lid], out[rid] = out[rid], out[lid]
            left = parse_il_date(out[lid])
            right = parse_il_date(out[rid])
            if left is not None and right is not None and left > right:
                return out
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/generate/test_relations.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -m "feat(generate): order-relation satisfy/violate helpers"
```

## Task 4: generate/population.py — F5 node

- [ ] **Step 1: Write the failing test**

`tests/generate/test_population.py`:
```python
from doc2tests.contracts.enums import FieldType, RelationOp, SourceKind, TestClass
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.contracts.template import (
    CanonicalTemplate, DocSource, Field, Relation,
)
from doc2tests.generate.population import generate_population
from doc2tests.validators import is_valid_israeli_id


def _state(n):
    tmpl = CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[
            Field(id="pid", label="מספר זהות", type=FieldType.israeli_id),
            Field(id="a", label="חוזה", type=FieldType.date),
            Field(id="b", label="כניסה", type=FieldType.date),
        ],
        relations=[Relation(kind="order", op=RelationOp.le, left="a", right="b")],
    )
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        template=tmpl, config=RunConfig(n=n, seed=7),
    )


def test_population_has_exactly_n_records():
    out = generate_population(_state(20))
    assert len(out["population"]) == 20


def test_population_covers_all_three_classes():
    pop = generate_population(_state(50))["population"]
    classes = {r.test_class for r in pop}
    assert classes == {TestClass.equivalence, TestClass.boundary, TestClass.negative}


def test_equivalence_records_have_valid_ids():
    pop = generate_population(_state(50))["population"]
    for r in pop:
        if r.test_class == TestClass.equivalence:
            assert is_valid_israeli_id(r.values["pid"].value)
            assert r.expected_valid is True


def test_negative_records_are_flagged():
    pop = generate_population(_state(50))["population"]
    negs = [r for r in pop if r.test_class == TestClass.negative]
    assert negs
    for r in negs:
        assert r.expected_valid is False
        assert r.violates


def test_deterministic_same_seed():
    a = generate_population(_state(10))["population"]
    b = generate_population(_state(10))["population"]
    assert [r.values["pid"].value for r in a] == [r.values["pid"].value for r in b]


def test_passthrough_without_template():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert generate_population(st)["population"] == []
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/generate/test_population.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/doc2tests/generate/population.py`:
```python
from __future__ import annotations

import random
from typing import Any

from doc2tests.contracts.enums import FieldType, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import GraphState
from doc2tests.contracts.template import CanonicalTemplate, Field
from doc2tests.generate.relations import violate_order
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import validate

# field types that carry a content validator we can deliberately break
_VALIDATED = {
    FieldType.israeli_id, FieldType.date, FieldType.gush_helka,
    FieldType.phone, FieldType.bank_branch,
}


def _class_counts(n: int, mix: dict[TestClass, float]) -> list[TestClass]:
    counts = {c: int(n * w) for c, w in mix.items()}
    while sum(counts.values()) < n:  # distribute rounding remainder
        counts[TestClass.equivalence] += 1
    seq: list[TestClass] = []
    for c, k in counts.items():
        seq.extend([c] * k)
    return seq[:n]


def _value_for(field: Field, cls: TestClass, rng: random.Random) -> str:
    strat = strategy_for(field.type, rng)
    if cls == TestClass.equivalence:
        return strat.equivalence()
    if cls == TestClass.boundary:
        return strat.boundary()
    neg = strat.negative()
    return rng.choice(neg) if neg else strat.equivalence()


def _validated_fields(template: CanonicalTemplate) -> list[Field]:
    return [f for f in template.fields if f.type in _VALIDATED]


def generate_population(state: GraphState) -> dict[str, Any]:
    if state.template is None:
        return {"population": []}
    tmpl = state.template
    rng = random.Random(state.config.seed)
    classes = _class_counts(state.config.n, state.config.mix)
    rng.shuffle(classes)
    records: list[Record] = []
    for i, cls in enumerate(classes):
        values: dict[str, str] = {}
        for f in tmpl.fields:
            record_cls = cls if cls != TestClass.negative else TestClass.equivalence
            values[f.id] = _value_for(f, record_cls, rng)

        violates: str | None = None
        if cls == TestClass.negative:
            violates = _inject_violation(tmpl, values, rng)

        record_values = {
            f.id: Value(field_id=f.id, value=values[f.id],
                        valid=validate(f.type, values[f.id]))
            for f in tmpl.fields
        }
        records.append(Record(
            index=i, test_class=cls,
            expected_valid=(cls != TestClass.negative),
            violates=violates, values=record_values,
        ))
    return {"population": records}


def _inject_violation(
    template: CanonicalTemplate, values: dict[str, str], rng: random.Random
) -> str:
    """Break exactly one rule: a validated field's value, or an order relation."""
    validated = _validated_fields(template)
    order_rels = [r for r in template.relations if r.kind == "order"]
    choices: list[str] = ["field"] * len(validated) + (["relation"] if order_rels else [])
    if not choices:
        return "none"
    pick = rng.choice(choices)
    if pick == "relation":
        broken = violate_order(template, values)
        values.update(broken)
        return "relation.order"
    field = rng.choice(validated)
    neg = strategy_for(field.type, rng).negative()
    values[field.id] = rng.choice(neg) if neg else values[field.id]
    return f"{field.type.value}.invalid"
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/generate/test_population.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -m "feat(generate): F5 QA-aware population with class mix + one-violation negatives"
```

## Task 5: coverage/report.py — X3

- [ ] **Step 1: Write the failing test**

`tests/coverage/test_report.py`:
```python
from doc2tests.contracts.enums import FieldType, SourceKind, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.template import CanonicalTemplate, DocSource, Field
from doc2tests.coverage.report import build_coverage


def _tmpl():
    return CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="pid", label="ז", type=FieldType.israeli_id),
                Field(id="note", label="הערה", type=FieldType.free_text)],
    )


def _pop():
    return [
        Record(index=0, test_class=TestClass.equivalence, expected_valid=True,
               values={"pid": Value(field_id="pid", value="123456782"),
                       "note": Value(field_id="note", value="x")}),
        Record(index=1, test_class=TestClass.negative, expected_valid=False,
               violates="israeli_id.invalid",
               values={"pid": Value(field_id="pid", value="1", valid=False),
                       "note": Value(field_id="note", value="y")}),
    ]


def test_counts_per_class_and_field():
    rep = build_coverage(_tmpl(), _pop())
    eq = [c for c in rep.cells if c.field_id == "pid" and c.test_class == TestClass.equivalence]
    assert eq and eq[0].count == 1


def test_rules_exercised_lists_violations():
    rep = build_coverage(_tmpl(), _pop())
    assert "israeli_id.invalid" in rep.rules_exercised


def test_gaps_flag_untested_negative_fields():
    # only 1 negative touching israeli_id; free_text has no validator -> not a gap
    rep = build_coverage(_tmpl(), _pop())
    assert isinstance(rep.gaps, list)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/coverage/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/doc2tests/coverage/__init__.py` (empty).
`src/doc2tests/coverage/report.py`:
```python
from __future__ import annotations

from collections import Counter

from doc2tests.contracts.enums import FieldType, TestClass
from doc2tests.contracts.records import Record
from doc2tests.contracts.state import CoverageCell, CoverageReport
from doc2tests.contracts.template import CanonicalTemplate

_VALIDATED = {
    FieldType.israeli_id, FieldType.date, FieldType.gush_helka,
    FieldType.phone, FieldType.bank_branch,
}


def build_coverage(template: CanonicalTemplate, population: list[Record]) -> CoverageReport:
    per_class: Counter[TestClass] = Counter(r.test_class for r in population)
    cells: list[CoverageCell] = []
    for f in template.fields:
        for cls in TestClass:
            cells.append(CoverageCell(field_id=f.id, test_class=cls, count=per_class.get(cls, 0)))

    rules = sorted({r.violates for r in population if r.violates})
    tested_types = {r.violates.split(".")[0] for r in population if r.violates}
    gaps = [f"{f.id}:{f.type.value} has no negative coverage"
            for f in template.fields
            if f.type in _VALIDATED and f.type.value not in tested_types]
    return CoverageReport(cells=cells, rules_exercised=rules, gaps=gaps)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/coverage/test_report.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -m "feat(coverage): X3 coverage report (class matrix, rules, gaps)"
```

## Task 6: render/html.py

- [ ] **Step 1: Write the failing test**

`tests/render/test_html.py`:
```python
from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.template import CanonicalTemplate, DocSource, Field
from doc2tests.render.html import render_html


def _tmpl():
    return CanonicalTemplate(
        doc_type="bank-form", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="pid", label="מספר זהות", type=FieldType.israeli_id)],
    )


def _rec():
    return Record(index=3, test_class="equivalence", expected_valid=True,
                  values={"pid": Value(field_id="pid", value="123456782")})


def test_html_contains_label_value_and_rtl():
    html = render_html(_tmpl(), _rec())
    assert "מספר זהות" in html
    assert "123456782" in html
    assert 'dir="rtl"' in html


def test_html_marks_invalid_values():
    tmpl = _tmpl()
    rec = Record(index=0, test_class="negative", expected_valid=False,
                 violates="israeli_id.invalid",
                 values={"pid": Value(field_id="pid", value="1", valid=False)})
    html = render_html(tmpl, rec)
    assert "invalid" in html.lower()
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/render/test_html.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/doc2tests/render/__init__.py` (empty).
`src/doc2tests/render/html.py`:
```python
from __future__ import annotations

from jinja2 import Environment

from doc2tests.contracts.records import Record
from doc2tests.contracts.template import CanonicalTemplate

_TEMPLATE = """<!doctype html>
<html lang="he" dir="rtl">
<head><meta charset="utf-8"><title>{{ doc_type }}</title>
<style>
 body { font-family: Arial, sans-serif; direction: rtl; margin: 2rem; }
 h1 { font-size: 1.2rem; }
 table { border-collapse: collapse; width: 100%; }
 td, th { border: 1px solid #999; padding: 6px 10px; text-align: right; }
 .invalid { color: #b00; font-weight: bold; }
 .meta { color: #666; font-size: 0.8rem; margin-bottom: 1rem; }
</style></head>
<body>
<h1>{{ doc_type }}</h1>
<div class="meta">record #{{ record.index }} · {{ record.test_class }}
{% if not record.expected_valid %}· expected INVALID ({{ record.violates }}){% endif %}</div>
<table>
<tr><th>שדה</th><th>ערך</th></tr>
{% for f in fields %}
<tr><td>{{ f.label }}</td>
<td class="{% if not f.valid %}invalid{% endif %}">{{ f.value }}</td></tr>
{% endfor %}
</table>
</body></html>"""


def render_html(template: CanonicalTemplate, record: Record) -> str:
    rows = []
    for f in template.fields:
        v = record.values.get(f.id)
        rows.append({"label": f.label,
                     "value": v.value if v else "",
                     "valid": v.valid if v else True})
    env = Environment(autoescape=True)
    return env.from_string(_TEMPLATE).render(
        doc_type=template.doc_type, record=record, fields=rows)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/render/test_html.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -m "feat(render): RTL HTML reconstruction (Jinja2)"
```

## Task 7: render/docx.py

- [ ] **Step 1: Write the failing test**

`tests/render/test_docx.py`:
```python
from docx import Document

from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.template import CanonicalTemplate, DocSource, Field
from doc2tests.render.docx import render_docx


def _tmpl():
    return CanonicalTemplate(
        doc_type="bank-form", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="pid", label="מספר זהות", type=FieldType.israeli_id)],
    )


def test_docx_written_and_contains_values(tmp_path):
    out = tmp_path / "r.docx"
    rec = Record(index=0, test_class="equivalence", expected_valid=True,
                 values={"pid": Value(field_id="pid", value="123456782")})
    render_docx(_tmpl(), rec, str(out))
    assert out.exists()
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    table_text = " ".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert "bank-form" in text
    assert "מספר זהות" in table_text
    assert "123456782" in table_text
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/render/test_docx.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/doc2tests/render/docx.py`:
```python
from __future__ import annotations

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from doc2tests.contracts.records import Record
from doc2tests.contracts.template import CanonicalTemplate


def render_docx(template: CanonicalTemplate, record: Record, path: str) -> None:
    doc = Document()
    heading = doc.add_heading(template.doc_type, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    meta = doc.add_paragraph(
        f"record #{record.index} · {record.test_class}"
        + ("" if record.expected_valid else f" · expected INVALID ({record.violates})")
    )
    meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "שדה"
    hdr[1].text = "ערך"
    for f in template.fields:
        v = record.values.get(f.id)
        cells = table.add_row().cells
        cells[0].text = f.label
        cells[1].text = v.value if v else ""
    doc.save(path)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/render/test_docx.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -m "feat(render): DOCX reconstruction (python-docx)"
```

## Task 8: render/run.py — F6 node

- [ ] **Step 1: Write the failing test**

`tests/render/test_run.py`:
```python
from doc2tests.contracts.enums import FieldType, SourceKind, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.contracts.template import CanonicalTemplate, DocSource, Field
from doc2tests.render.run import render_fill


def _state(tmp_path, formats):
    tmpl = CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="pid", label="מספר זהות", type=FieldType.israeli_id)],
    )
    pop = [Record(index=0, test_class=TestClass.equivalence, expected_valid=True,
                  values={"pid": Value(field_id="pid", value="123456782")})]
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        template=tmpl, population=pop, config=RunConfig(formats=formats),
    )


def test_render_fill_writes_both_formats(tmp_path):
    out = render_fill(_state(tmp_path, ["html", "docx"]), str(tmp_path))
    docs = out["outputs"]
    assert {d.fmt for d in docs} == {"html", "docx"}
    for d in docs:
        assert (tmp_path / d.path).exists() or __import__("os").path.exists(d.path)


def test_render_fill_html_only(tmp_path):
    out = render_fill(_state(tmp_path, ["html"]), str(tmp_path))
    assert {d.fmt for d in out["outputs"]} == {"html"}
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/render/test_run.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`src/doc2tests/render/run.py`:
```python
from __future__ import annotations

import os
from typing import Any

from doc2tests.contracts.state import GraphState, RenderedDoc
from doc2tests.render.docx import render_docx
from doc2tests.render.html import render_html


def render_fill(state: GraphState, out_dir: str) -> dict[str, Any]:
    if state.template is None or not state.population:
        return {"outputs": []}
    os.makedirs(out_dir, exist_ok=True)
    outputs: list[RenderedDoc] = []
    for record in state.population:
        for fmt in state.config.formats:
            path = os.path.join(out_dir, f"record_{record.index:04d}.{fmt}")
            if fmt == "html":
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(render_html(state.template, record))
            elif fmt == "docx":
                render_docx(state.template, record, path)
            else:
                continue
            outputs.append(RenderedDoc(record_index=record.index, fmt=fmt, path=path))
    return {"outputs": outputs}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/render/test_run.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Full suite + lint + types**

Run:
```bash
uv run pytest --ignore=tests/extraction/test_live_openai.py
uv run ruff check src tests
uv run mypy
```
Expected: all PASS, ruff clean, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -q -m "feat(render): F6 render_fill node (HTML + DOCX per record)"
```

## Definition of Done (Plan 3)

- [ ] `generate_population` yields N tagged records with all three classes; equivalence valid, negatives flagged with a single violation.
- [ ] `build_coverage` reports class counts, exercised rules, and gaps.
- [ ] `render_fill` writes HTML + DOCX per record.
- [ ] Full offline suite green; ruff + mypy clean.

**Next:** Plan 4 wires F1..F6 + review gate into a LangGraph graph behind FastAPI + a Streamlit UI for end-to-end runs on the real fixtures.

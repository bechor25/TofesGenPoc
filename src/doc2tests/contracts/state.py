from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field as PField

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
    # per-field inferred notes keyed by field id; relations live on the template
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
    field_schema: FieldSchema | None = None
    review: ReviewDecision | None = None
    population: list[Record] = PField(default_factory=list)
    coverage: CoverageReport | None = None
    outputs: list[RenderedDoc] = PField(default_factory=list)
    errors: list[StageError] = PField(default_factory=list)

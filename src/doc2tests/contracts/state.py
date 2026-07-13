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

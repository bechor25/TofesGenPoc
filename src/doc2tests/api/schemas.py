"""Pydantic v2 request/response contracts for the API, plus mappers to/from the
pipeline's internal ``DetectedValue``. Kept separate so the wire shape is explicit
and the React types (``frontend/src/api/types.ts``) mirror it 1:1."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from doc2tests.common.slug import unique_slug
from doc2tests.contracts.enums import FieldType
from doc2tests.contracts.state import DetectedValue


class DetectedDTO(BaseModel):
    id: str
    label: str
    value: str
    field_type: str
    is_personal: bool
    slot: str | None = None

    @classmethod
    def from_detected(cls, d: DetectedValue) -> DetectedDTO:
        return cls(id=d.id, label=d.label, value=d.value,
                   field_type=d.field_type.value, is_personal=d.is_personal,
                   slot=d.slot)


class ColumnDTO(BaseModel):
    """One value-column of the variants table: a personal field to replace."""
    id: str
    label: str


class VariantDTO(BaseModel):
    index: int
    values: dict[str, str]  # field id -> generated value
    rendered: bool = False


class DiagnosticsRowDTO(BaseModel):
    label: str
    field_type: str
    is_personal: bool
    slot: str | None
    original: str
    generated: str


class DocStateDTO(BaseModel):
    """The full current state of a worked document — the SPA refetches this after
    every job (extract fills ``detected``; generate fills ``variants``/``diagnostics``;
    render flips ``rendered``)."""
    doc_id: str
    filename: str
    doc_summary: str
    page_image_url: str | None
    detected: list[DetectedDTO]
    columns: list[ColumnDTO]
    variants: list[VariantDTO]
    diagnostics: list[DiagnosticsRowDTO]


class ReviewedValueDTO(BaseModel):
    label: str
    value: str
    field_type: str = "free_text"
    is_personal: bool = False
    slot: str | None = None


class GenerateReq(BaseModel):
    values: list[ReviewedValueDTO]
    n: int = 10


class RenderReq(BaseModel):
    variant_index: int
    difficulty: int = 1  # 1-10 recognition-difficulty score for the test image


class JobRef(BaseModel):
    job_id: str
    doc_id: str | None = None


class JobStatusDTO(BaseModel):
    id: str
    status: str
    error: str | None = None
    result: Any = None


class SourceDTO(BaseModel):
    id: int
    filename: str
    doc_summary: str
    n_generated: int
    has_page_image: bool = False
    has_detected: bool = False


class OpenResult(BaseModel):
    """Result of opening a stored source to run the flow. ``cached`` = the extraction was
    reused (no job); otherwise poll ``job_id`` for the extraction job."""
    doc_id: str
    job_id: str | None = None
    cached: bool = False


class UploadResult(BaseModel):
    source_ids: list[int]


class GeneratedDTO(BaseModel):
    id: int
    variant_index: int
    values: dict[str, Any]
    difficulty: int = 1


class BatchItemDTO(BaseModel):
    doc_id: str
    filename: str
    n_variants: int
    error: str | None = None


def reviewed_to_detected(values: list[ReviewedValueDTO]) -> list[DetectedValue]:
    """Turn the user's reviewed rows into detected values with stable unique ids —
    the same id/slug logic the old Streamlit review gate used, so generation is
    unchanged. Blank rows are dropped; a bad field_type falls back to free_text."""
    out: list[DetectedValue] = []
    seen: list[str] = []
    for r in values:
        label = r.label.strip()
        val = r.value.strip()
        if not label and not val:
            continue
        fid = unique_slug(label or val, seen)
        seen.append(fid)
        try:
            ftype = FieldType(r.field_type or "free_text")
        except ValueError:
            ftype = FieldType.free_text
        slot = r.slot.strip() if r.slot else ""
        out.append(DetectedValue(
            id=fid, label=label, value=val, field_type=ftype,
            is_personal=r.is_personal, slot=slot or None))
    return out

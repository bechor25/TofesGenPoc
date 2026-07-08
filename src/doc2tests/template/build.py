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

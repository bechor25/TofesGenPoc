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
        ftype, _pii, pii_type = classify_value(pf.label, pf.value)
        fid = unique_slug(pf.label or pf.value or "field", seen)
        seen.append(fid)
        # Replace only person/case-specific data (the extractor's semantic judgment),
        # never static form scaffolding — and never a blank field. The review gate lets
        # the user override any decision.
        is_personal = pf.personal and bool(pf.value.strip())
        out.append(DetectedValue(
            id=fid, label=pf.label, value=pf.value, field_type=ftype,
            is_personal=is_personal, pii_type=pii_type,
            value_kind=pf.value_kind, bbox=pf.bbox,
        ))
    return {"detected": out}

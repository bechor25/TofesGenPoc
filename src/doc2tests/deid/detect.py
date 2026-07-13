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
        # Every filled-in value is case-specific and must be replaced — not just a
        # narrow PII whitelist. A blank field has nothing to replace. The review gate
        # lets the user untick anything that should stay (e.g. a static form number).
        is_personal = bool(pf.value.strip())
        out.append(DetectedValue(
            id=fid, label=pf.label, value=pf.value, field_type=ftype,
            is_personal=is_personal, pii_type=pii_type,
            value_kind=pf.value_kind, bbox=pf.bbox,
        ))
    return {"detected": out}

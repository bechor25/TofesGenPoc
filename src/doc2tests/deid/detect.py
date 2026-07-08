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

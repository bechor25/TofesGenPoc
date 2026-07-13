from __future__ import annotations

from typing import Any

from doc2tests.common.logging import get_logger
from doc2tests.common.slug import unique_slug
from doc2tests.contracts.enums import FieldType, PiiType
from doc2tests.contracts.state import DetectedValue, GraphState
from doc2tests.deid.classify import classify_value

_log = get_logger("detect")

# pii label for a type the MODEL assigned (the value-shape classifier supplies its own).
_PII_FOR: dict[FieldType, PiiType] = {
    FieldType.hebrew_name: PiiType.PERSON,
    FieldType.israeli_id: PiiType.IL_ID,
    FieldType.date: PiiType.DATE,
    FieldType.address: PiiType.LOCATION,
    FieldType.phone: PiiType.PHONE,
}


def detect_fields(state: GraphState) -> dict[str, Any]:
    if state.parse_result is None:
        return {"detected": []}
    out: list[DetectedValue] = []
    seen: list[str] = []
    for pf in state.parse_result.fields:
        # Dynamic first: trust the model's content-based type. The keyword/value-shape
        # classifier is only a fallback when the model gave no type — so nothing hinges
        # on a specific label string.
        ftype, _pii, pii_type = classify_value(pf.label, pf.value)
        if pf.field_type is not None:
            ftype = pf.field_type
            pii_type = _PII_FOR.get(ftype, PiiType.OTHER)
        fid = unique_slug(pf.label or pf.value or "field", seen)
        seen.append(fid)
        # Replace only person/case-specific data (the extractor's semantic judgment),
        # never static form scaffolding — and never a blank field. The review gate lets
        # the user override any decision.
        is_personal = pf.personal and bool(pf.value.strip())
        out.append(DetectedValue(
            id=fid, label=pf.label, value=pf.value, field_type=ftype,
            is_personal=is_personal, pii_type=pii_type,
            value_kind=pf.value_kind, slot=pf.slot, bbox=pf.bbox,
        ))
    # per-field trace: label -> type -> replace? -> value. This is where a field's
    # fate is decided, so log every one to diagnose mis-typings end to end.
    n_personal = sum(1 for d in out if d.is_personal)
    _log.info("detect: %d field(s), %d to REPLACE / %d KEEP",
              len(out), n_personal, len(out) - n_personal)
    for d in out:
        tag = "REPLACE" if d.is_personal else "KEEP   "
        _log.info("  detect | %s | %-16s | %r = %r",
                  tag, d.field_type.value, d.label, d.value)
    return {"detected": out}

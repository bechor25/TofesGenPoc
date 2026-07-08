from __future__ import annotations

from doc2tests.contracts.enums import FieldType, PiiType
from doc2tests.validators import is_valid_il_date, is_valid_israeli_id

_NAME_HINTS = ("שם", "name")
_ID_HINTS = ("זהות", "ת.ז", 'ת"ז', "ז.ה", "tz")
_DATE_HINTS = ("תאריך", "date")
_GUSH_HINTS = ("גוש", "חלקה", "gush")
_PHONE_HINTS = ("טלפון", "phone", "נייד")
_BRANCH_HINTS = ("סניף", "branch")
_ASSESS_HINTS = ("שומה", "assessment")


def _has(label: str, hints: tuple[str, ...]) -> bool:
    low = label.lower()
    return any(h.lower() in low for h in hints)


def classify_value(label: str, value: str) -> tuple[FieldType, bool, PiiType | None]:
    """Type a field. Label-first: the printed label signals the semantic type,
    which is robust to OCR errors in a (handwritten) value. Content validators
    are a fallback only when the label carries no signal — checksums exist to
    validate *generated* values, not to classify the field."""
    v = value.strip()
    # label-first
    if _has(label, _ID_HINTS):
        return FieldType.israeli_id, True, PiiType.IL_ID
    if _has(label, _GUSH_HINTS):
        return FieldType.gush_helka, False, None
    if _has(label, _ASSESS_HINTS):
        return FieldType.assessment_number, False, None
    if _has(label, _BRANCH_HINTS):
        return FieldType.bank_branch, False, None
    if _has(label, _PHONE_HINTS):
        return FieldType.phone, True, PiiType.PHONE
    if _has(label, _DATE_HINTS):
        return FieldType.date, False, PiiType.DATE
    if _has(label, _NAME_HINTS):
        return FieldType.hebrew_name, True, PiiType.PERSON
    # no label signal: fall back to value content
    if v and is_valid_israeli_id(v) and len(v.replace(" ", "")) == 9:
        return FieldType.israeli_id, True, PiiType.IL_ID
    if v and is_valid_il_date(v):
        return FieldType.date, False, PiiType.DATE
    return FieldType.free_text, False, None

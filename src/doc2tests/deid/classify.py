from __future__ import annotations

from doc2tests.contracts.enums import FieldType, PiiType
from doc2tests.validators import (
    is_valid_gush_helka,
    is_valid_il_date,
    is_valid_il_phone,
    is_valid_israeli_id,
)

_NAME_HINTS = ("שם", "name")
_ID_HINTS = ("זהות", "ת.ז", 'ת"ז', "id")
_DATE_HINTS = ("תאריך", "date")
_GUSH_HINTS = ("גוש", "חלקה", "gush")
_PHONE_HINTS = ("טלפון", "phone", "נייד")
_BRANCH_HINTS = ("סניף", "branch")
_ASSESS_HINTS = ("שומה", "assessment")


def _has(label: str, hints: tuple[str, ...]) -> bool:
    low = label.lower()
    return any(h.lower() in low for h in hints)


def classify_value(label: str, value: str) -> tuple[FieldType, bool, PiiType | None]:
    v = value.strip()
    # strongest signal: content validators
    if v and is_valid_israeli_id(v) and (_has(label, _ID_HINTS) or len(v.replace(" ", "")) == 9):
        return FieldType.israeli_id, True, PiiType.IL_ID
    if v and _has(label, _GUSH_HINTS) and is_valid_gush_helka(v):
        return FieldType.gush_helka, False, None
    if v and _has(label, _PHONE_HINTS) and is_valid_il_phone(v):
        return FieldType.phone, True, PiiType.PHONE
    if v and (is_valid_il_date(v) and _has(label, _DATE_HINTS)):
        return FieldType.date, False, PiiType.DATE
    if _has(label, _ASSESS_HINTS):
        return FieldType.assessment_number, False, None
    if _has(label, _BRANCH_HINTS):
        return FieldType.bank_branch, False, None
    if _has(label, _NAME_HINTS):
        return FieldType.hebrew_name, True, PiiType.PERSON
    return FieldType.free_text, False, None

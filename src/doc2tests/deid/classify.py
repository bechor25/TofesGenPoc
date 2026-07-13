from __future__ import annotations

import re

from doc2tests.contracts.enums import FieldType, PiiType
from doc2tests.validators import is_valid_il_date, is_valid_israeli_id

_NAME_HINTS = ("שם", "name", "לכבוד", "נמען", "מקבל", "מבקש", "רוכש", "מוכר")
_ID_HINTS = ("זהות", "ת.ז", 'ת"ז', "ז.ה", "tz")
_DATE_HINTS = ("תאריך", "date")
_GUSH_HINTS = ("גוש", "חלקה", "gush")
_PHONE_HINTS = ("טלפון", "phone", "נייד", "פקס", "fax")
_BRANCH_HINTS = ("סניף", "branch")
_ASSESS_HINTS = ("שומה", "assessment", "מספר", "number", "אסמכתא", "קבלה", "תיק")
# NB: no bare "מען" here — it is a substring of "נמען" (recipient = a NAME), and since
# address is matched before name, it would mis-type the recipient name as an address.
# "כתובת נמען" still classifies as address via the explicit "כתובת".
_ADDR_HINTS = ("כתובת", "רחוב", "עיר", "ישוב", "יישוב", "address", "street", "city")

# value-shape patterns (used when the label carries no semantic signal)
_PHONE_RE = re.compile(r"^0\d{1,2}[-\s]?\d{6,7}$")
_DATE_RE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")
_NUMERIC_RE = re.compile(r"^[\d][\d\-/.\s]*\d$")


def _has(label: str, hints: tuple[str, ...]) -> bool:
    low = label.lower()
    return any(h.lower() in low for h in hints)


def _digits(v: str) -> str:
    return re.sub(r"\D", "", v)


def classify_value(label: str, value: str) -> tuple[FieldType, bool, PiiType | None]:
    """Type a field. Label-first (the printed label is the strongest signal and is
    robust to OCR errors in a handwritten value); then value-shape as a fallback when
    the label carries no signal. Note: whether a value gets REPLACED is decided by
    ``detect_fields`` (any filled value is replaceable) — this only picks a type so a
    plausible replacement can be generated."""
    v = value.strip()

    # --- label-first ---
    if _has(label, _ID_HINTS):
        return FieldType.israeli_id, True, PiiType.IL_ID
    if _has(label, _GUSH_HINTS):
        # combined "1234-56-7" vs a single component (גוש alone = a plain number)
        combined = ("-" in v or "/" in v
                    or (_has(label, ("גוש",)) and _has(label, ("חלקה",))))
        if combined:
            return FieldType.gush_helka, False, PiiType.OTHER
        return FieldType.assessment_number, False, PiiType.OTHER
    if _has(label, _BRANCH_HINTS):
        return FieldType.bank_branch, False, PiiType.OTHER
    if _has(label, _PHONE_HINTS):
        return FieldType.phone, True, PiiType.PHONE
    if _has(label, _ADDR_HINTS):
        return FieldType.address, True, PiiType.LOCATION
    if _has(label, _DATE_HINTS):
        return FieldType.date, True, PiiType.DATE
    if _has(label, _NAME_HINTS):
        return FieldType.hebrew_name, True, PiiType.PERSON
    if _has(label, _ASSESS_HINTS):
        return FieldType.assessment_number, False, PiiType.OTHER

    # --- value-shape fallback (label missing or noisy) ---
    if _PHONE_RE.match(v):
        return FieldType.phone, True, PiiType.PHONE
    if len(_digits(v)) == 9 and is_valid_israeli_id(_digits(v)):
        return FieldType.israeli_id, True, PiiType.IL_ID
    if _DATE_RE.match(v) or is_valid_il_date(v):
        return FieldType.date, True, PiiType.DATE
    if _NUMERIC_RE.match(v) and len(_digits(v)) >= 3:
        return FieldType.assessment_number, False, PiiType.OTHER
    return FieldType.free_text, False, None

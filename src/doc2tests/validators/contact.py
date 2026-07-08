from __future__ import annotations

import re

_DIGITS = re.compile(r"\D")


def _only_digits(value: str) -> str:
    return _DIGITS.sub("", value)


def is_valid_il_phone(value: str) -> bool:
    d = _only_digits(value)
    # Israeli numbers: 9 (landline) or 10 (mobile) digits, leading 0
    return d.startswith("0") and len(d) in (9, 10)


def is_valid_bank_branch(value: str) -> bool:
    d = value.strip()
    return d.isdigit() and 1 <= len(d) <= 3

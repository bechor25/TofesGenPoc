from __future__ import annotations

from datetime import date


def parse_il_date(value: str) -> date | None:
    s = value.strip()
    for sep in (".", "/", "-"):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3:
                d, m, y = parts
                return _build(d, m, y)
            return None
    if s.isdigit() and len(s) == 4:
        try:
            return date(int(s), 1, 1)
        except ValueError:
            return None
    return None


def _build(d: str, m: str, y: str) -> date | None:
    if not (d.isdigit() and m.isdigit() and y.isdigit()):
        return None
    year = int(y)
    if year < 100:                     # two-digit year -> 2000s
        year += 2000
    try:
        return date(year, int(m), int(d))
    except ValueError:
        return None


def is_valid_il_date(value: str) -> bool:
    return parse_il_date(value) is not None

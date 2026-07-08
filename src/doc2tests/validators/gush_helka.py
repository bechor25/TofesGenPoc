from __future__ import annotations

import re

_PARTS = re.compile(r"\d+")


def _tokens(value: str) -> list[str]:
    return _PARTS.findall(value.strip())


def is_valid_gush_helka(value: str) -> bool:
    parts = _tokens(value)
    if len(parts) < 2 or len(parts) > 3:
        return False
    gush, helka = parts[0], parts[1]
    # tokens are numeric by construction (regex \d+); enforce length bounds
    return 1 <= len(gush) <= 6 and 1 <= len(helka) <= 4


def normalize_gush_helka(value: str) -> str:
    parts = _tokens(value)
    if len(parts) < 2:
        raise ValueError("gush/helka requires at least two numeric parts")
    stripped = [str(int(p)) for p in parts[:3]]
    return "-".join(stripped)

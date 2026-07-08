from __future__ import annotations


def _checksum_total(digits9: str) -> int:
    total = 0
    for i, ch in enumerate(digits9):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n if n < 10 else n - 9
    return total


def is_valid_israeli_id(value: str) -> bool:
    s = value.strip()
    if not s.isdigit() or len(s) > 9:
        return False
    s = s.zfill(9)
    return _checksum_total(s) % 10 == 0


def complete_israeli_id(prefix8: str) -> str:
    if not prefix8.isdigit() or len(prefix8) > 8:
        raise ValueError("prefix must be up to 8 digits")
    base = prefix8.zfill(8) + "0"
    remainder = _checksum_total(base) % 10
    check = (10 - remainder) % 10
    return prefix8.zfill(8) + str(check)

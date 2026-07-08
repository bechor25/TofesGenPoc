from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

_NON_ASCII = re.compile(r"[^a-z0-9]+")


def _stable_suffix(label: str) -> int:
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()
    return int(digest[:4], 16) % 10000


def slugify(label: str) -> str:
    ascii_only = label.strip().lower().encode("ascii", "ignore").decode("ascii")
    slug = _NON_ASCII.sub("_", ascii_only).strip("_")
    return slug or f"field_{_stable_suffix(label)}"


def unique_slug(label: str, seen: Iterable[str]) -> str:
    seen_set = set(seen)
    base = slugify(label)
    if base not in seen_set:
        return base
    i = 2
    while f"{base}_{i}" in seen_set:
        i += 1
    return f"{base}_{i}"

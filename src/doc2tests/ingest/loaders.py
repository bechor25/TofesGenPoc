"""Format detection. Rasterization lives in ingest/rasterize.py."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

Kind = Literal["image", "pdf", "docx"]

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def detect_kind(path: str) -> Kind:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".docx", ".doc"):
        return "docx"
    if ext in _IMAGE_EXT:
        return "image"
    raise ValueError(f"unsupported file type: {ext or path}")

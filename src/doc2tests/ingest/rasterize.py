"""Turn any supported input (image / pdf / word) into page images (PNG bytes).
This is the single entry the image-edit pipeline needs: the model edits an image,
so every input kind is normalized to a page image first."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from doc2tests.common.logging import get_logger
from doc2tests.ingest.loaders import detect_kind

_log = get_logger("rasterize")
_MAX_PAGES = 3
_SOFFICE_FALLBACK = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def soffice_path() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    return _SOFFICE_FALLBACK if Path(_SOFFICE_FALLBACK).exists() else None


def _to_png(data: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _pdf_to_png(path: str, dpi: int = 200) -> list[bytes]:
    import fitz  # PyMuPDF

    pages: list[bytes] = []
    with fitz.open(path) as doc:
        for page in doc[:_MAX_PAGES]:
            pages.append(page.get_pixmap(dpi=dpi).tobytes("png"))
    return pages


def _docx_to_pdf(path: str, out_dir: str) -> str:
    soffice = soffice_path()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice (soffice) not found — install it to accept Word documents, "
            "or supply a PDF/image instead."
        )
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, path],
        check=True, capture_output=True, timeout=120,
    )
    pdf = Path(out_dir) / (Path(path).stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError(f"soffice did not produce a PDF for {path}")
    return str(pdf)


def rasterize(path: str) -> list[bytes]:
    """Return page images (PNG bytes) for image, pdf, or word input."""
    kind = detect_kind(path)
    if kind == "image":
        return [_to_png(Path(path).read_bytes())]
    if kind == "pdf":
        return _pdf_to_png(path)
    if kind == "docx":
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _docx_to_pdf(path, tmp)
            pages = _pdf_to_png(pdf)
        _log.info("rasterized word -> %d page image(s)", len(pages))
        return pages
    raise ValueError(f"unsupported kind: {kind}")

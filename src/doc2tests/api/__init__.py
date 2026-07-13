"""FastAPI backend for the image-edit pipeline.

A thin JSON + SSE layer over the UNCHANGED pipeline stage functions
(``ingest_parse -> detect_fields -> generate_population -> render_variant``).
Slow work runs as in-process background jobs; live status streams over SSE from
the shared log buffer. The React SPA (``frontend/dist``) is served as static files.
"""
from __future__ import annotations

from doc2tests.api.app import create_app

app = create_app()

__all__ = ["app", "create_app"]

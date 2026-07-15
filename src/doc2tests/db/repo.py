"""Persistence for source originals and the images generated from them.

The whole layer is OPTIONAL and best-effort: with no reachable DATABASE_URL every call
degrades gracefully (returns None / empty), so the app runs fine without a database.
Set DATABASE_URL (PostgreSQL in docker-compose, or a SQLite file) to enable it.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from doc2tests.common.logging import get_logger
from doc2tests.db.models import Base, GeneratedDocument, SourceDocument

_log = get_logger("db")

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


# --- detached read rows (safe to use after the session closes) ----------------------
@dataclass
class SourceRow:
    id: int
    filename: str
    doc_summary: str
    created_at: datetime | None
    n_generated: int
    has_page_image: bool = False
    has_detected: bool = False


@dataclass
class SourceFull:
    """A source loaded for RUNNING the flow: the page image + any cached extraction."""
    id: int
    filename: str
    doc_summary: str
    page_image: bytes | None
    detected: list[dict[str, Any]] | None


@dataclass
class GeneratedRow:
    id: int
    variant_index: int
    values: dict[str, Any]
    created_at: datetime | None


def _session_factory() -> sessionmaker[Session] | None:
    """Lazily connect + create tables. Returns None (once) if no/unreachable DB."""
    global _engine, _Session
    if _Session is not None:
        return _Session
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    try:
        _engine = create_engine(url, future=True, pool_pre_ping=True)
        Base.metadata.create_all(_engine)
        _ensure_schema(_engine)
        _Session = sessionmaker(bind=_engine, future=True)
        _log.info("db connected: %s", url.rsplit("@", 1)[-1])
        return _Session
    except Exception as exc:  # noqa: BLE001 - DB is optional; never crash the app
        _log.warning("db unavailable (%s) — persistence disabled", exc)
        return None


def _ensure_schema(engine: Engine) -> None:
    """Lightweight forward migration for columns added after a DB was first created
    (``create_all`` never ALTERs existing tables). Idempotent — adds ``detected`` to an
    existing ``source_document`` so a live pgdata volume keeps working without a reset."""
    cols = {c["name"] for c in inspect(engine).get_columns("source_document")}
    if "detected" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE source_document ADD COLUMN detected JSON"))
        _log.info("db migrate: added source_document.detected")


def available() -> bool:
    return _session_factory() is not None


def reset() -> None:
    """Drop the cached engine/session (tests point DATABASE_URL elsewhere)."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_source(
    filename: str, page_image: bytes | None, doc_summary: str = ""
) -> int | None:
    """Upsert a source by content hash; return its unique id (None if DB is off)."""
    factory = _session_factory()
    if factory is None:
        return None
    key = _hash(page_image if page_image else filename.encode("utf-8"))
    try:
        with factory() as s, s.begin():
            existing = s.scalar(
                select(SourceDocument).where(SourceDocument.content_hash == key))
            if existing is not None:
                if doc_summary and not existing.doc_summary:
                    existing.doc_summary = doc_summary
                return existing.id
            row = SourceDocument(filename=filename, content_hash=key,
                                 doc_summary=doc_summary, page_image=page_image)
            s.add(row)
            s.flush()
            return row.id
    except Exception as exc:  # noqa: BLE001 - persistence must never break generation
        _log.warning("save_source failed (%s)", exc)
        return None


def save_generated(
    source_id: int, variant_index: int, values: dict[str, Any], image: bytes
) -> int | None:
    """Upsert one generated image for (source, variant). Returns its id (None if off)."""
    factory = _session_factory()
    if factory is None:
        return None
    try:
        with factory() as s, s.begin():
            existing = s.scalar(select(GeneratedDocument).where(
                GeneratedDocument.source_id == source_id,
                GeneratedDocument.variant_index == variant_index))
            if existing is not None:
                existing.values = values
                existing.image = image
                return existing.id
            row = GeneratedDocument(source_id=source_id, variant_index=variant_index,
                                    values=values, image=image)
            s.add(row)
            s.flush()
            return row.id
    except Exception as exc:  # noqa: BLE001
        _log.warning("save_generated failed (%s)", exc)
        return None


def list_sources() -> list[SourceRow]:
    factory = _session_factory()
    if factory is None:
        return []
    with factory() as s:
        count_rows = s.execute(
            select(GeneratedDocument.source_id, func.count(GeneratedDocument.id))
            .group_by(GeneratedDocument.source_id)).all()
        counts = {int(sid): int(c) for sid, c in count_rows}
        # select scalar columns + null-checks only — never load the page-image blobs here
        rows = s.execute(
            select(SourceDocument.id, SourceDocument.filename,
                   SourceDocument.doc_summary, SourceDocument.created_at,
                   SourceDocument.page_image.isnot(None),
                   SourceDocument.detected.isnot(None))
            .order_by(SourceDocument.created_at.desc())).all()
        return [SourceRow(id=r[0], filename=r[1], doc_summary=r[2], created_at=r[3],
                          n_generated=counts.get(r[0], 0),
                          has_page_image=bool(r[4]), has_detected=bool(r[5]))
                for r in rows]


def get_source(source_id: int) -> SourceFull | None:
    """Load a source for RUNNING the flow: its page image + any cached extraction."""
    factory = _session_factory()
    if factory is None:
        return None
    with factory() as s:
        row = s.get(SourceDocument, source_id)
        if row is None:
            return None
        return SourceFull(
            id=row.id, filename=row.filename, doc_summary=row.doc_summary,
            page_image=bytes(row.page_image) if row.page_image is not None else None,
            detected=list(row.detected) if row.detected else None)


def set_extraction(
    source_id: int, doc_summary: str, detected: list[dict[str, Any]]
) -> None:
    """Cache the extraction (detected values + summary) under a source, so re-running the
    flow reuses it instead of paying for gpt-5.1 again. Updated with the reviewed values
    on generate, so a user's edits stick to the next run. Best-effort."""
    factory = _session_factory()
    if factory is None:
        return
    try:
        with factory() as s, s.begin():
            row = s.get(SourceDocument, source_id)
            if row is None:
                return
            if doc_summary:
                row.doc_summary = doc_summary
            row.detected = detected
    except Exception as exc:  # noqa: BLE001 - persistence must never break the flow
        _log.warning("set_extraction failed (%s)", exc)


def list_generated(source_id: int) -> list[GeneratedRow]:
    factory = _session_factory()
    if factory is None:
        return []
    with factory() as s:
        rows = s.scalars(select(GeneratedDocument)
                         .where(GeneratedDocument.source_id == source_id)
                         .order_by(GeneratedDocument.variant_index)).all()
        return [GeneratedRow(id=r.id, variant_index=r.variant_index,
                             values=dict(r.values or {}), created_at=r.created_at)
                for r in rows]


def list_generated_images(source_id: int) -> list[bytes]:
    """All generated images for a source, ordered by variant — for a 'download all' zip."""
    factory = _session_factory()
    if factory is None:
        return []
    with factory() as s:
        rows = s.scalars(
            select(GeneratedDocument.image)
            .where(GeneratedDocument.source_id == source_id)
            .order_by(GeneratedDocument.variant_index)).all()
        return [bytes(r) for r in rows if r is not None]


def get_image(generated_id: int) -> bytes | None:
    factory = _session_factory()
    if factory is None:
        return None
    with factory() as s:
        row = s.get(GeneratedDocument, generated_id)
        return bytes(row.image) if row and row.image is not None else None

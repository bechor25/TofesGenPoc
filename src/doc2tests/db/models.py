"""Relational schema: a SOURCE document (the uploaded original, with a unique id) has
many GENERATED documents (the images produced from it). Portable column types (JSON,
LargeBinary) so the same models run on PostgreSQL (compose) and SQLite (tests)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, LargeBinary, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class SourceDocument(Base):
    """One uploaded original. ``id`` is the unique number shown in the UI; every image
    generated from it points back here via ``source_id``."""
    __tablename__ = "source_document"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, unique=True, index=True)
    doc_summary: Mapped[str] = mapped_column(Text, default="")
    page_image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # cached extraction (list of DetectedValue dicts) so re-running the flow on a stored
    # source reuses it instead of paying for gpt-5.1 again. None = not yet extracted.
    detected: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    generated: Mapped[list[GeneratedDocument]] = relationship(
        back_populates="source", cascade="all, delete-orphan",
        order_by="GeneratedDocument.variant_index",
    )


class GeneratedDocument(Base):
    """One image produced from a source, for a given data variant."""
    __tablename__ = "generated_document"
    __table_args__ = (UniqueConstraint("source_id", "variant_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE"), index=True)
    # a running number within the source (max+1 on insert), so the test bank ACCUMULATES
    # — many images per source across runs/difficulties, none overwritten.
    variant_index: Mapped[int] = mapped_column()
    # recognition-difficulty score (1-10) the image was rendered at; 1 = clean copy.
    difficulty: Mapped[int] = mapped_column(default=1, server_default="1")
    values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    image: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    source: Mapped[SourceDocument] = relationship(back_populates="generated")

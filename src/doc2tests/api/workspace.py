"""Server-side, in-memory working state for a document across the multi-step flow
(extract -> review/generate -> render). Mirrors the old Streamlit ``session_state``,
but on the server. Ephemeral: lost on restart — durable output is persisted to the
DB on render, exactly as before."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from doc2tests.contracts.batch import DocumentResult
from doc2tests.contracts.records import Record
from doc2tests.contracts.state import DetectedValue


@dataclass
class Workspace:
    doc_id: str
    filename: str
    page_image: bytes | None = None
    detected: list[DetectedValue] = field(default_factory=list)
    doc_summary: str = ""
    population: list[Record] = field(default_factory=list)
    rendered: dict[int, bytes] = field(default_factory=dict)
    source_id: int | None = None


class WorkspaceStore:
    """Thread-safe map of ``doc_id -> Workspace``. doc_ids are a monotonic counter
    (``doc-1``, ``doc-2``, …) so they are deterministic and easy to test."""

    def __init__(self) -> None:
        self._items: dict[str, Workspace] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def new(self, filename: str) -> str:
        with self._lock:
            self._counter += 1
            doc_id = f"doc-{self._counter}"
            self._items[doc_id] = Workspace(doc_id=doc_id, filename=filename)
        return doc_id

    def get(self, doc_id: str) -> Workspace:
        """Return the workspace or raise KeyError (routes convert that to 404)."""
        return self._items[doc_id]

    def as_document_result(self, doc_id: str) -> DocumentResult:
        ws = self.get(doc_id)
        return DocumentResult(
            path=ws.filename, detected=ws.detected, population=ws.population,
            page_image=ws.page_image, doc_summary=ws.doc_summary)

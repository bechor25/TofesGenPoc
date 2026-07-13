"""Central logging. One configured logger tree under ``doc2tests``; each pipeline
node logs what it did so runs are traceable and failures surface with context."""
from __future__ import annotations

import logging
import os
from collections import deque

_CONFIGURED = False
_BUFFER: deque[str] = deque(maxlen=500)
_SEQ = 0  # total lines ever emitted — a monotonic marker the UI uses to scope a run


class _BufferHandler(logging.Handler):
    """Keep recent log lines in memory so the UI can display the run's logs."""

    def emit(self, record: logging.LogRecord) -> None:
        global _SEQ
        _BUFFER.append(self.format(record))
        _SEQ += 1


def configure(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    lvl = (level or os.getenv("DOC2TESTS_LOG_LEVEL") or "INFO").upper()
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    buffer = _BufferHandler()
    buffer.setFormatter(fmt)
    root = logging.getLogger("doc2tests")
    root.setLevel(getattr(logging, lvl, logging.INFO))
    root.handlers.clear()
    root.addHandler(stream)
    root.addHandler(buffer)
    root.propagate = False
    _CONFIGURED = True


def recent_logs(n: int = 120) -> list[str]:
    return list(_BUFFER)[-n:]


def log_marker() -> int:
    """A snapshot of how many lines have been emitted — pass to ``logs_since`` to read
    only the lines produced AFTER this point (so a UI status ignores stale history)."""
    return _SEQ


def logs_since(marker: int) -> list[str]:
    """Log lines emitted since ``marker`` (best-effort — bounded by the 500-line buffer)."""
    new = _SEQ - marker
    if new <= 0:
        return []
    return list(_BUFFER)[-min(new, len(_BUFFER)):]


def get_logger(name: str) -> logging.Logger:
    configure()
    return logging.getLogger(f"doc2tests.{name}")

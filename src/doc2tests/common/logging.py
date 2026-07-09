"""Central logging. One configured logger tree under ``doc2tests``; each pipeline
node logs what it did so runs are traceable and failures surface with context."""
from __future__ import annotations

import logging
import os
from collections import deque

_CONFIGURED = False
_BUFFER: deque[str] = deque(maxlen=500)


class _BufferHandler(logging.Handler):
    """Keep recent log lines in memory so the UI can display the run's logs."""

    def emit(self, record: logging.LogRecord) -> None:
        _BUFFER.append(self.format(record))


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


def get_logger(name: str) -> logging.Logger:
    configure()
    return logging.getLogger(f"doc2tests.{name}")

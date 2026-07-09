"""Central logging. One configured logger tree under ``doc2tests``; each pipeline
node logs what it did so runs are traceable and failures surface with context."""
from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    lvl = (level or os.getenv("DOC2TESTS_LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S"))
    root = logging.getLogger("doc2tests")
    root.setLevel(getattr(logging, lvl, logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure()
    return logging.getLogger(f"doc2tests.{name}")

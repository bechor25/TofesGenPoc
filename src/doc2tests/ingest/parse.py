from __future__ import annotations

from typing import Any

from doc2tests.common.logging import get_logger
from doc2tests.contracts.state import GraphState, ParseResult, StageError
from doc2tests.ingest.grounded import extract_grounded
from doc2tests.ingest.rasterize import rasterize
from doc2tests.providers.base import LLMProvider

_log = get_logger("ingest")


def ingest_parse(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    """Rasterize any input to page images, then run the two-stage grounded
    extraction (transcribe -> structure) at FULL resolution to catch the most
    values (small digits, handwriting)."""
    path = state.input_ref.path
    try:
        images = rasterize(path)
        raw_text, doc_summary, fields = extract_grounded(images, provider)
        _log.info("ingest_parse: %d page(s) -> %d fields via %s",
                  len(images), len(fields), provider.name)
        return {
            "page_images": images,
            "parse_result": ParseResult(
                raw_text=raw_text, doc_summary=doc_summary, fields=fields,
                provider=provider.name),
        }
    except Exception as exc:  # noqa: BLE001 - node boundary converts errors to state
        _log.exception("ingest_parse failed for %s", path)
        return {
            "parse_result": ParseResult(provider=provider.name),
            "errors": [StageError(stage="ingest_parse", message=str(exc))],
        }

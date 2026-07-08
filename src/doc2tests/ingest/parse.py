from __future__ import annotations

from typing import Any

from doc2tests.common.json_utils import extract_json
from doc2tests.contracts.enums import ValueKind
from doc2tests.contracts.state import GraphState, ParsedField, ParseResult, StageError
from doc2tests.contracts.template import BBox
from doc2tests.ingest.loaders import detect_kind, load_images, read_docx_text
from doc2tests.providers.base import LLMProvider

_SCHEMA = (
    'Return ONLY a JSON object with keys: '
    '"raw_text" (string, all visible text), and '
    '"fields" (array). Each field: '
    '{"label": <the printed field label>, "value": <the filled-in value, "" if blank>, '
    '"value_kind": "printed" | "handwritten", '
    '"bbox": {"page":1,"x":0..1,"y":0..1,"w":0..1,"h":0..1} | null }. '
    "Do not include commentary."
)
VISION_PROMPT = (
    "You are a document parser. Read this scanned/photographed form (Hebrew, RTL). " + _SCHEMA
)
TEXT_PROMPT = (
    "You are a document parser. Below is the text of a Hebrew form/document. "
    "Identify its labelled fields and their values. " + _SCHEMA + "\n\nDOCUMENT TEXT:\n"
)


def _bbox(raw: dict[str, Any] | None) -> BBox | None:
    if not raw:
        return None
    try:
        return BBox(page=int(raw.get("page", 1)), x=float(raw["x"]), y=float(raw["y"]),
                    w=float(raw["w"]), h=float(raw["h"]))
    except (KeyError, TypeError, ValueError):
        return None


def _parse_fields(text: str) -> tuple[str, list[ParsedField]]:
    data = extract_json(text)
    fields: list[ParsedField] = []
    for f in data.get("fields", []):
        kind = (ValueKind.handwritten if f.get("value_kind") == "handwritten"
                else ValueKind.printed)
        fields.append(ParsedField(
            label=str(f.get("label", "")),
            value=str(f.get("value", "")),
            value_kind=kind,
            bbox=_bbox(f.get("bbox")),
        ))
    return str(data.get("raw_text", "")), fields


def ingest_parse(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    """F1: route by input format.
    image/pdf -> vision extraction; docx -> text-LLM extraction."""
    path = state.input_ref.path
    try:
        if detect_kind(path) == "docx":
            text = read_docx_text(path)
            resp = provider.complete_text(TEXT_PROMPT + text, json_mode=True)
        else:  # image or pdf (rendered to page images)
            images = load_images(path)
            resp = provider.extract_vision(images, VISION_PROMPT, json_mode=True)
        raw_text, fields = _parse_fields(resp.text)
        return {"parse_result": ParseResult(
            raw_text=raw_text, fields=fields, provider=provider.name)}
    except Exception as exc:  # noqa: BLE001 - node boundary converts errors to state
        return {
            "parse_result": ParseResult(provider=provider.name),
            "errors": [StageError(stage="ingest_parse", message=str(exc))],
        }

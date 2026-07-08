from __future__ import annotations

from pathlib import Path
from typing import Any

from doc2tests.common.json_utils import extract_json
from doc2tests.contracts.enums import ValueKind
from doc2tests.contracts.state import GraphState, ParsedField, ParseResult, StageError
from doc2tests.contracts.template import BBox
from doc2tests.providers.base import LLMProvider

VISION_PROMPT = (
    "You are a document parser. Read this scanned/photographed form (Hebrew, RTL). "
    "Return ONLY a JSON object with keys: "
    '"raw_text" (string, all visible text), and '
    '"fields" (array). Each field: '
    '{"label": <the printed field label>, "value": <the filled-in value, "" if blank>, '
    '"value_kind": "printed" | "handwritten", '
    '"bbox": {"page":1,"x":0..1,"y":0..1,"w":0..1,"h":0..1} | null }. '
    "Do not include commentary."
)


def _bbox(raw: dict[str, Any] | None) -> BBox | None:
    if not raw:
        return None
    try:
        return BBox(page=int(raw.get("page", 1)), x=float(raw["x"]), y=float(raw["y"]),
                    w=float(raw["w"]), h=float(raw["h"]))
    except (KeyError, TypeError, ValueError):
        return None


def ingest_parse(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    try:
        image_bytes = Path(state.input_ref.path).read_bytes()
        resp = provider.extract_vision([image_bytes], VISION_PROMPT, json_mode=True)
        data = extract_json(resp.text)
        fields = []
        for f in data.get("fields", []):
            kind = (ValueKind.handwritten if f.get("value_kind") == "handwritten"
                    else ValueKind.printed)
            fields.append(ParsedField(
                label=str(f.get("label", "")),
                value=str(f.get("value", "")),
                value_kind=kind,
                bbox=_bbox(f.get("bbox")),
            ))
        return {"parse_result": ParseResult(
            raw_text=str(data.get("raw_text", "")), fields=fields, provider=provider.name)}
    except Exception as exc:  # noqa: BLE001 - node boundary converts errors to state
        return {
            "parse_result": ParseResult(provider=provider.name),
            "errors": [StageError(stage="ingest_parse", message=str(exc))],
        }

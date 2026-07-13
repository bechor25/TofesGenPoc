"""Two-stage grounded extraction — the reliable pattern for Hebrew KIE.

Pass 1 (TRANSCRIBE): the vision model transcribes EVERY text element with its
bounding box and printed/handwritten kind — a grounded OCR of the page.

Pass 2 (STRUCTURE): pair each field label with its value, CONSTRAINED to the
pass-1 text so the model cannot invent values. Grounding both reduces hallucinated
values and yields real bboxes (usable later for masked image editing).

Works with any vision provider (local Qwen3-VL via Ollama, or OpenAI).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from doc2tests.common.json_utils import extract_json
from doc2tests.common.logging import get_logger
from doc2tests.contracts.enums import ValueKind
from doc2tests.contracts.state import ParsedField
from doc2tests.contracts.template import BBox
from doc2tests.providers.base import LLMProvider

_log = get_logger("grounded")

_TRANSCRIBE_PROMPT = (
    "TRANSCRIBE TASK. You are a precise OCR engine for Hebrew forms (right-to-left). "
    "Transcribe EVERY text element on the page — printed and handwritten — exactly as "
    "written; do not translate, paraphrase, or guess. Return ONLY JSON: "
    '{"lines":[{"text":<exact text>,'
    '"bbox":{"x":0..1,"y":0..1,"w":0..1,"h":0..1},'
    '"kind":"printed"|"handwritten"}]}. '
    "x,y = top-right corner of the text region (RTL), normalized 0..1 of the image. "
    "Include short tokens (numbers, dates) as their own lines. No commentary."
)

_STRUCTURE_PROMPT = (
    "STRUCTURE TASK. Below are text lines already transcribed from a Hebrew form, each "
    "with a position. Pair every field LABEL with its filled-in VALUE. A value is "
    "variable / case-specific information: person or company names, id numbers, dates, "
    "amounts, phone numbers, addresses, גוש/חלקה parcel numbers, reference/assessment "
    "numbers. CRITICAL: every value MUST be copied verbatim from the lines below — never "
    "invent or complete a value that is not present. Also include labelled fields that "
    "are blank (value \"\"). Return ONLY JSON: "
    '{"raw_text":<all text joined>,'
    '"fields":[{"label":<label text>,"value":<value text>,'
    '"value_kind":"printed"|"handwritten",'
    '"bbox":{"x":0..1,"y":0..1,"w":0..1,"h":0..1}|null}]}. '
    "No commentary.\n\nLINES:\n"
)


@dataclass
class Line:
    text: str
    bbox: BBox | None
    kind: ValueKind


def _bbox(raw: dict[str, Any] | None) -> BBox | None:
    if not raw:
        return None
    try:
        return BBox(page=int(raw.get("page", 1)), x=float(raw["x"]), y=float(raw["y"]),
                    w=float(raw["w"]), h=float(raw["h"]))
    except (KeyError, TypeError, ValueError):
        return None


def _kind(v: Any) -> ValueKind:
    return ValueKind.handwritten if v == "handwritten" else ValueKind.printed


def transcribe(images: list[bytes], provider: LLMProvider) -> list[Line]:
    resp = provider.extract_vision(images, _TRANSCRIBE_PROMPT, json_mode=True)
    data = extract_json(resp.text)
    lines: list[Line] = []
    for ln in data.get("lines", []):
        text = str(ln.get("text", "")).strip()
        if not text:
            continue
        lines.append(Line(text=text, bbox=_bbox(ln.get("bbox")),
                          kind=_kind(ln.get("kind"))))
    _log.info("grounded transcribe: %d line(s)", len(lines))
    return lines


def _lines_payload(lines: list[Line]) -> str:
    import json
    rows = [{"text": ln.text, "kind": ln.kind.value,
             "bbox": (ln.bbox.model_dump() if ln.bbox else None)} for ln in lines]
    return json.dumps(rows, ensure_ascii=False)


def structure(
    lines: list[Line], images: list[bytes], provider: LLMProvider
) -> tuple[str, list[ParsedField]]:
    prompt = _STRUCTURE_PROMPT + _lines_payload(lines)
    resp = provider.extract_vision(images, prompt, json_mode=True)
    data = extract_json(resp.text)
    fields: list[ParsedField] = []
    for f in data.get("fields", []):
        fields.append(ParsedField(
            label=str(f.get("label", "")), value=str(f.get("value", "")),
            value_kind=_kind(f.get("value_kind")), bbox=_bbox(f.get("bbox")),
        ))
    raw = str(data.get("raw_text", "")) or " ".join(ln.text for ln in lines)
    _log.info("grounded structure: %d field(s)", len(fields))
    return raw, fields


def extract_grounded(
    images: list[bytes], provider: LLMProvider
) -> tuple[str, list[ParsedField]]:
    lines = transcribe(images, provider)
    return structure(lines, images, provider)

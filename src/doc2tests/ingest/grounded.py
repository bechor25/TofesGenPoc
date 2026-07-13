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
from doc2tests.contracts.enums import FieldType, ValueKind
from doc2tests.contracts.state import ParsedField
from doc2tests.contracts.template import BBox
from doc2tests.providers.base import LLMProvider

_log = get_logger("grounded")

# Map the model's semantic type words (content-based, dynamic — NOT label keywords) onto
# our generator types. Aliases are accepted so the model isn't forced into exact enum
# spellings; anything unknown falls through to None -> value-shape classifier fallback.
_TYPE_ALIASES: dict[str, FieldType] = {
    "name": FieldType.hebrew_name, "person": FieldType.hebrew_name,
    "hebrew_name": FieldType.hebrew_name, "company": FieldType.hebrew_name,
    "id": FieldType.israeli_id, "israeli_id": FieldType.israeli_id, "tz": FieldType.israeli_id,
    "date": FieldType.date,
    "phone": FieldType.phone,
    "address": FieldType.address, "location": FieldType.address,
    "gush_helka": FieldType.gush_helka, "gush": FieldType.gush_helka,
    "assessment_number": FieldType.assessment_number, "number": FieldType.assessment_number,
    "reference": FieldType.assessment_number,
    "bank_branch": FieldType.bank_branch, "branch": FieldType.bank_branch,
    "currency": FieldType.currency, "amount": FieldType.currency, "money": FieldType.currency,
    "free_text": FieldType.free_text, "text": FieldType.free_text,
}


def _field_type(v: Any) -> FieldType | None:
    if not v:
        return None
    return _TYPE_ALIASES.get(str(v).strip().lower())

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
    "UNDERSTAND & STRUCTURE TASK. Below are text lines already transcribed from a Hebrew "
    "form, each with a position. You are a document-understanding agent.\n"
    "FIRST, grasp the WHOLE document. In a \"doc\" field write ONE sentence (Hebrew): what "
    "this form is, its purpose, and — for THIS specific document — what kind of data on it "
    "is personal/case-specific vs static office scaffolding. Use that understanding to "
    "judge every field below; it is dynamic per document, not a fixed rule.\n"
    "THEN pair every field LABEL with its filled-in VALUE. CRITICAL: every value MUST be "
    "copied verbatim from the lines below — never invent or complete a value that is not "
    "present. Also include labelled fields that are blank (value \"\").\n"
    "For EACH field set \"personal\": true or false.\n"
    "  personal=true  — data that identifies a specific PERSON or a specific CASE and "
    "would differ on another person's copy of this form: patient/applicant/party names "
    "and surnames, id numbers (ת\"ז), personal/home address, age, date of birth, personal "
    "phone, the medical diagnosis / reason / description / finding (הבחנה/אבחנה/סיבה/תיאור), "
    "case dates and amounts, the case's גוש/חלקה, seller/buyer details.\n"
    "  personal=false — STATIC form scaffolding printed by the issuing office that stays "
    "identical on every copy: the institution/office name (e.g. רשות המסים, ביטוח לאומי), "
    "office address and office phone, section headings and table COLUMN LABELS, "
    "form/barcode/reference numbers printed by the office, reception hours, general "
    "instructions, the signing clerk's title.\n"
    "When unsure, prefer false (keep the form scaffolding intact).\n"
    "For EACH field also set \"type\" — the KIND of the VALUE, judged from the value's "
    "content and role, NOT guessed from the label wording. Choose exactly one of: "
    "\"name\" (a person or company name), \"id\" (Israeli id / ת\"ז, ~9 digits), \"date\", "
    "\"phone\", \"address\" (a street / city / settlement where a person lives), "
    "\"gush_helka\" (block-parcel land id), \"assessment_number\" (any other reference / "
    "case / receipt / file / barcode number), \"currency\" (a money amount), "
    "\"free_text\" (a diagnosis / reason / description, or any other free text). "
    "Judge by what the value IS: e.g. \"הרצל 5 חיפה\" is address even if its label is "
    "\"נמען\"; \"עלי זועבי\" is name even with no label.\n"
    "For EACH field also set \"slot\" — a short key naming the real-world VALUE, so the "
    "filled form stays COHERENT. Fields that are the SAME entity printed more than once "
    "MUST share one slot (a recipient name printed twice → same slot; a repeated address "
    "line → the SAME slot as its duplicate line). Genuinely different values get "
    "different slots. Keep distinct parts distinct: address line 1 and line 2 are "
    "DIFFERENT slots; buyer and seller are DIFFERENT slots.\n"
    "Return ONLY JSON: "
    '{"doc":<one Hebrew sentence>,"raw_text":<all text joined>,'
    '"fields":[{"label":<label text>,"value":<value text>,'
    '"personal":true|false,"type":<one type above>,"slot":<short key>,'
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


def _slot(v: Any) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


def structure(
    lines: list[Line], images: list[bytes], provider: LLMProvider
) -> tuple[str, str, list[ParsedField]]:
    """Return (raw_text, doc_summary, fields). doc_summary is the agent's big-picture
    grasp of the document; fields carry personal/type/slot decisions made in that light."""
    prompt = _STRUCTURE_PROMPT + _lines_payload(lines)
    resp = provider.extract_vision(images, prompt, json_mode=True)
    data = extract_json(resp.text)
    fields: list[ParsedField] = []
    for f in data.get("fields", []):
        fields.append(ParsedField(
            label=str(f.get("label", "")), value=str(f.get("value", "")),
            value_kind=_kind(f.get("value_kind")),
            personal=bool(f.get("personal", True)),
            field_type=_field_type(f.get("type")), slot=_slot(f.get("slot")),
            bbox=_bbox(f.get("bbox")),
        ))
    raw = str(data.get("raw_text", "")) or " ".join(ln.text for ln in lines)
    doc_summary = str(data.get("doc", "")).strip()
    _log.info("grounded structure: %d field(s)", len(fields))
    if doc_summary:
        _log.info("  understand | %s", doc_summary)
    return raw, doc_summary, fields


def extract_grounded(
    images: list[bytes], provider: LLMProvider
) -> tuple[str, str, list[ParsedField]]:
    lines = transcribe(images, provider)
    return structure(lines, images, provider)

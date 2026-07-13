"""Data agent — writes REALISTIC fake values for free-text fields.

Structured fields (id, date, phone, numbers) are produced by local validators that
guarantee valid, well-formed output. But descriptive free-text fields — a diagnosis, a
complaint, a finding, a reason — have no local generator that yields believable content:
faker only emits lorem-ipsum gibberish, which reads as broken Hebrew.

This agent asks the model to write believable, human-readable values that keep each
field's MEANING and FORMAT (a diagnosis stays a plausible diagnosis; '32Y 2M' → another
age; a Hebrew clinical note → another Hebrew clinical note), across N distinct variants,
in one call — conditioned on the document's purpose so the content fits the form.
"""
from __future__ import annotations

import json

from doc2tests.common.json_utils import extract_json
from doc2tests.common.logging import get_logger
from doc2tests.contracts.state import DetectedValue
from doc2tests.providers.base import LLMProvider

_log = get_logger("data_agent")

_SYSTEM = (
    "You generate realistic FAKE data to populate an Israeli form for testing. Every "
    "value must be believable and human-readable — NEVER lorem-ipsum, placeholder text, "
    "or nonsense words. Match the language, register, and format of each field's example."
)


def _prompt(fields: list[DetectedValue], doc_summary: str, n: int) -> str:
    rows = [{"id": f.id, "label": f.label, "example": f.value} for f in fields]
    return (
        f"Document: {doc_summary or 'an Israeli form'}.\n"
        f"For EACH field below, generate {n} DISTINCT, realistic values. Rules:\n"
        "- Keep each value's MEANING and KIND like the example: a medical diagnosis → "
        "another plausible diagnosis; a complaint → another realistic complaint; a "
        "finding → another realistic finding; '32Y 2M' → another age like '47Y 3M'; a "
        "time '14:43:28' → another time.\n"
        "- Use Hebrew when the example is Hebrew, and keep the clinical/formal register.\n"
        "- Believable content ONLY — no lorem-ipsum, no gibberish, no placeholders.\n"
        f'Return ONLY JSON {{"fields":{{"<id>":["v1", ..., "v{n}"], ...}}}}.'
        "\n\nFIELDS:\n" + json.dumps(rows, ensure_ascii=False)
    )


def generate_text_variants(
    fields: list[DetectedValue], doc_summary: str, n: int, provider: LLMProvider
) -> dict[str, list[str]]:
    """Return {field_id: [up to n realistic values]}. Best-effort — on any failure
    returns {} so the caller falls back to local generation."""
    if not fields or n < 1:
        return {}
    try:
        # pre-call marker so a live UI shows this stage DURING the model call
        _log.info("data agent: writing realistic values for %d field(s)...", len(fields))
        resp = provider.complete_text(
            _prompt(fields, doc_summary, n), system=_SYSTEM, json_mode=True)
        data = extract_json(resp.text)
        ids = {f.id for f in fields}
        out: dict[str, list[str]] = {}
        for fid, vals in (data.get("fields") or {}).items():
            if str(fid) in ids and isinstance(vals, list):
                clean = [str(v).strip() for v in vals if str(v).strip()]
                if clean:
                    out[str(fid)] = clean
        _log.info("data agent: realistic variants for %d/%d free-text field(s)",
                  len(out), len(fields))
        return out
    except Exception as exc:  # noqa: BLE001 - realism is best-effort; degrade to local
        _log.warning("data agent failed (%s) — free-text falls back to local", exc)
        return {}

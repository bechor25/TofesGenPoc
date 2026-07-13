from __future__ import annotations

from dataclasses import dataclass

from doc2tests.common.logging import get_logger
from doc2tests.providers.base import LLMProvider

_log = get_logger("imagegen")

_INSTRUCTION = (
    "You are a precise document-image editor for official Israeli forms "
    "(medical, National Insurance / ביטוח לאומי, bank, tax). You receive one "
    "scanned or photographed form. Reproduce it EXACTLY — identical layout, fonts, "
    "colors, stamps, table lines, and handwriting style — changing ONLY the personal "
    "values listed below. For each pair, find the OLD value in the image and replace it "
    "with the NEW value, matching the original script (Hebrew, right-to-left), the same "
    "printed-vs-handwritten style, size, and position. Do NOT alter any label, static "
    "text, logo, or any value not listed. Keep everything else pixel-identical. Output "
    "the full edited form."
)


@dataclass(frozen=True)
class Replacement:
    old: str
    new: str


def build_edit_prompt(replacements: list[Replacement], doc_hint: str = "") -> str:
    lines = [_INSTRUCTION]
    if doc_hint:
        lines.append(f"Document type hint: {doc_hint}.")
    pairs = [r for r in replacements if r.old.strip() and r.old != r.new]
    if pairs:
        lines.append("Replacements (OLD → NEW):")
        lines += [f'- "{r.old}" → "{r.new}"' for r in pairs]
    return "\n".join(lines)


def edit_form_image(
    original_png: bytes, replacements: list[Replacement], provider: LLMProvider,
    doc_hint: str = "",
) -> bytes:
    prompt = build_edit_prompt(replacements, doc_hint)
    pairs = [r for r in replacements if r.old.strip() and r.old != r.new]
    _log.info("editing image: %d value replacement(s)", len(pairs))
    for r in pairs:
        _log.info("  edit | %r -> %r", r.old, r.new)
    return provider.edit_image(original_png, prompt)

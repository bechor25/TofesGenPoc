"""Faithful digital RECREATION of the source document: the vision model rebuilds
the document as clean self-contained HTML that replicates its layout (titles,
tables, labels in place), with a Jinja2 ``{{ field_id }}`` placeholder in every
value slot. This is the reusable template — filled repeatedly with any data."""
from __future__ import annotations

import re
from collections.abc import Callable
from html import escape

from doc2tests.contracts.template import Field
from doc2tests.providers.base import LLMProvider


def _const(value: str) -> Callable[[re.Match[str]], str]:
    def repl(_m: re.Match[str]) -> str:
        return value
    return repl

_LAYOUT_PROMPT = (
    "Recreate this document as ONE self-contained, print-quality HTML page (inline CSS "
    "only) that visually REPLICATES the original as faithfully as possible: reproduce the "
    "same overall structure and proportions, the titles and sub-headers, the SAME tables "
    "with identical columns/rows and visible borders, text alignment, relative font sizes, "
    "bold/underline emphasis, and the position of every pre-printed field label. Use "
    'dir="rtl" and Hebrew.\n'
    "CRITICAL — this must be a BLANK TEMPLATE with NO personal data:\n"
    "• Keep ONLY the form's fixed scaffolding: titles, section headers, pre-printed field "
    "labels, table column headers, and boilerplate sentences — verbatim.\n"
    "• Replace EVERY variable / filled-in datum with a placeholder — this includes the "
    "recipient/addressee name, company, institution and address, all id/reference/receipt/"
    "assessment numbers, dates, amounts, phone numbers, גוש/חלקה/תת-חלקה numbers, and the "
    "names of any parties. Do NOT leave any real name, number, address or date in the "
    "output.\n"
    "• In each such value slot put EXACTLY one placeholder {{ field_id }} and nothing else, "
    "using ONLY these field ids (id: label):\n{fields}\n"
    "Do not invent new ids, do not output any real values, no commentary, no markdown "
    "fences. Output ONLY the HTML document."
)


def _strip_to_html(text: str) -> str:
    start = text.find("<")
    end = text.rfind(">")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()
    return text.strip()


def generate_layout_template(
    images: list[bytes], fields: list[Field], provider: LLMProvider
) -> str:
    """Ask the vision model to rebuild the document as fillable HTML."""
    field_lines = "\n".join(f"{f.id}: {f.label}" for f in fields)
    prompt = _LAYOUT_PROMPT.format(fields=field_lines)
    resp = provider.extract_vision(images, prompt, json_mode=False)
    return _strip_to_html(resp.text)


_DIGIT_RUN = re.compile(r"\d[\d./\- ]{3,}\d")  # 5+ chars: ids, postal, phone, dates


def deidentify_layout(html: str, value_by_id: dict[str, str], min_len: int = 3) -> str:
    """Deterministic safety net: replace any detected personal VALUE that leaked into
    the recreated template with its placeholder, so no real data remains. Short values
    (< min_len) are skipped to avoid over-matching. Then residual numeric PII (ids,
    postal codes, phones, dates) that the model kept as static text is redacted."""
    out = html
    # longest values first so a value that contains another is handled correctly
    for fid, val in sorted(value_by_id.items(), key=lambda kv: -len(kv[1].strip())):
        v = val.strip()
        if len(v) < min_len:
            continue
        token = f"{{{{ {fid} }}}}"
        for variant in (v, escape(v), " ".join(v.split())):
            out = out.replace(variant, token)
    return _redact_residual_numbers(out)


def _redact_residual_numbers(html: str) -> str:
    """Redact leftover multi-digit sequences — a blank template must contain no real
    id / postal / phone / date numbers. Placeholders ``{{ id }}`` are protected so
    digit-bearing field ids are never corrupted."""
    placeholders = re.findall(r"\{\{.*?\}\}", html)
    tmp = html
    for i, ph in enumerate(placeholders):
        tmp = tmp.replace(ph, f"\x00{i}\x00", 1)
    tmp = _DIGIT_RUN.sub("―――", tmp)
    for i, ph in enumerate(placeholders):
        tmp = tmp.replace(f"\x00{i}\x00", ph)
    return tmp


def fill_layout(template_html: str, values: dict[str, str]) -> str:
    """Substitute value placeholders. Robust to every brace/space variant the
    model emits — ``{{ id }}``, ``{{id}}``, ``{id}``, ``{ id }`` — matched per
    field id (CSS braces are untouched since ids never appear in them). Values are
    HTML-escaped. Pass empty strings to clear slots (blank template)."""
    out = template_html
    for fid, val in values.items():
        safe = escape(str(val))
        pattern = re.compile(r"\{+\s*" + re.escape(fid) + r"\s*\}+")
        out = pattern.sub(_const(safe), out)
    return out

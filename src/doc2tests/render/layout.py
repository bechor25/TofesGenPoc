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
    "Recreate this document as ONE self-contained HTML page (inline CSS only) that "
    "visually REPLICATES the original layout as faithfully as possible: the same overall "
    "structure, the same titles and sub-headers, the SAME tables with identical columns "
    "and rows, and every printed field label in its original position. Use dir=\"rtl\" and "
    "Hebrew. Keep every printed/static text (titles, headers, labels) verbatim. WHERE A "
    "FILLED-IN VALUE BELONGS, put EXACTLY one Jinja2 placeholder of the form {{ field_id }} "
    "in that cell and nothing else, using ONLY these field ids (id: label):\n"
    "{fields}\n"
    "Do not invent new ids, do not output any real values, do not add commentary or "
    "markdown fences. Output ONLY the HTML document."
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

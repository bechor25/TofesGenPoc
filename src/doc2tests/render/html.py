from __future__ import annotations

from html import escape

from doc2tests.contracts.records import Record
from doc2tests.contracts.template import CanonicalTemplate
from doc2tests.render.style import html_shell


def _meta(record: Record) -> str:
    cls = escape(str(record.test_class))
    parts = [f'<span class="badge badge--ok">רשומה #{record.index}</span>',
             f'<span class="badge">{cls}</span>']
    if not record.expected_valid:
        viol = escape(record.violates or "")
        parts.append(f'<span class="badge badge--bad">expected INVALID · {viol}</span>')
    return "".join(parts)


def render_html(template: CanonicalTemplate, record: Record) -> str:
    rows = []
    for f in template.fields:
        v = record.values.get(f.id)
        value = v.value if v else ""
        valid = v.valid if v else True
        cls = "value" if valid else "value value--invalid"
        rows.append(
            f'<tr><td class="label">{escape(f.label)}'
            f'<span class="tag">{escape(f.type.value)}</span></td>'
            f'<td><span class="{cls}">{escape(value)}</span></td></tr>'
        )
    foot = f"doc_type: {escape(template.doc_type)} · {len(template.fields)} שדות"
    return html_shell(template.doc_type, _meta(record), "\n".join(rows), foot)

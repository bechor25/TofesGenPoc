from __future__ import annotations

from jinja2 import Environment

from doc2tests.contracts.records import Record
from doc2tests.contracts.template import CanonicalTemplate

_TEMPLATE = """<!doctype html>
<html lang="he" dir="rtl">
<head><meta charset="utf-8"><title>{{ doc_type }}</title>
<style>
 body { font-family: Arial, sans-serif; direction: rtl; margin: 2rem; }
 h1 { font-size: 1.2rem; }
 table { border-collapse: collapse; width: 100%; }
 td, th { border: 1px solid #999; padding: 6px 10px; text-align: right; }
 .invalid { color: #b00; font-weight: bold; }
 .meta { color: #666; font-size: 0.8rem; margin-bottom: 1rem; }
</style></head>
<body>
<h1>{{ doc_type }}</h1>
<div class="meta">record #{{ record.index }} · {{ record.test_class }}
{% if not record.expected_valid %}· expected INVALID ({{ record.violates }}){% endif %}</div>
<table>
<tr><th>שדה</th><th>ערך</th></tr>
{% for f in fields %}
<tr><td>{{ f.label }}</td>
<td class="{% if not f.valid %}invalid{% endif %}">{{ f.value }}</td></tr>
{% endfor %}
</table>
</body></html>"""


def render_html(template: CanonicalTemplate, record: Record) -> str:
    rows = []
    for f in template.fields:
        v = record.values.get(f.id)
        rows.append({"label": f.label,
                     "value": v.value if v else "",
                     "valid": v.valid if v else True})
    env = Environment(autoescape=True)
    return env.from_string(_TEMPLATE).render(
        doc_type=template.doc_type, record=record, fields=rows)

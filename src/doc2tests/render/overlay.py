"""Exact-layout ("same constellation") rendering: keep the ORIGINAL document as
the visual background and replace only the value regions — with placeholders
(blank template) or with data (filled). Printed labels stay exactly where they
are; only the values are swapped. Output is self-contained HTML (RTL-correct)."""
from __future__ import annotations

import base64
from html import escape

from doc2tests.contracts.records import Record
from doc2tests.contracts.template import CanonicalTemplate

_CSS = """
*{box-sizing:border-box;}
body{margin:0;background:#eef1f6;padding:20px;
  font-family:'Assistant','Segoe UI',Arial,sans-serif;}
.wrap{max-width:900px;margin:0 auto;}
.bar{display:flex;gap:8px;align-items:center;margin-bottom:12px;direction:rtl;
  color:#1a2233;font-size:.85rem;}
.badge{background:#2b5cb8;color:#fff;border-radius:999px;padding:3px 11px;
  font-size:.72rem;font-weight:600;}
.badge--bad{background:#c0342b;}
.canvas{position:relative;width:100%;box-shadow:0 10px 30px rgba(20,30,60,.14);
  border-radius:8px;overflow:hidden;background:#fff;}
.canvas img{width:100%;display:block;}
.fld{position:absolute;display:flex;align-items:center;direction:rtl;
  padding:0 4px;overflow:hidden;background:#fff;border:1px solid #b9cdf0;
  color:#111;font-weight:700;white-space:nowrap;line-height:1;}
.fld.ph{background:#eef3fb;border-style:dashed;color:#2b5cb8;
  font-family:'SF Mono',Menlo,monospace;font-weight:500;}
.fld.bad{background:#fdecea;border-color:#e6a6a0;color:#c0342b;}
"""


def _data_uri(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _boxes(template: CanonicalTemplate, record: Record | None) -> str:
    parts: list[str] = []
    for f in template.fields:
        if f.bbox is None:
            continue
        b = f.bbox
        # font size scaled to box height (relative to a ~1000px-tall page)
        fs = max(9.0, min(28.0, b.h * 620))
        style = (f"left:{b.x * 100:.2f}%;top:{b.y * 100:.2f}%;"
                 f"width:{b.w * 100:.2f}%;height:{b.h * 100:.2f}%;font-size:{fs:.1f}px;")
        if record is None:
            parts.append(f'<div class="fld ph" style="{style}" '
                         f'title="{escape(f.label)}">{escape(f.placeholder)}</div>')
        else:
            v = record.values.get(f.id)
            value = v.value if v else ""
            cls = "fld" if (not v or v.valid) else "fld bad"
            parts.append(f'<div class="{cls}" style="{style}" '
                         f'title="{escape(f.label)}">{escape(value)}</div>')
    return "\n".join(parts)


def _meta(record: Record | None) -> str:
    if record is None:
        return '<span class="badge">טמפלייט — ללא ערכים</span>'
    cls = escape(str(record.test_class))
    bits = [f'<span class="badge">רשומה #{record.index} · {cls}</span>']
    if not record.expected_valid:
        viol = escape(record.violates or "")
        bits.append(f'<span class="badge badge--bad">INVALID · {viol}</span>')
    return "".join(bits)


def render_overlay_html(
    template: CanonicalTemplate,
    background: bytes,
    record: Record | None = None,
    *,
    mime: str = "image/jpeg",
) -> str:
    """Original document as background; value regions overlaid.

    record=None -> blank template (placeholders). record set -> filled."""
    title = f"{template.doc_type} — {'טמפלייט' if record is None else 'ממולא'}"
    return (
        '<!doctype html>\n<html lang="he" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title><style>{_CSS}</style></head><body><div class='wrap'>"
        f'<div class="bar">{_meta(record)}</div>'
        f'<div class="canvas"><img src="{_data_uri(background, mime)}" alt="source">'
        f"{_boxes(template, record)}</div></div></body></html>"
    )


def has_overlay(template: CanonicalTemplate) -> bool:
    """True when enough fields carry bounding boxes to place an overlay."""
    return any(f.bbox is not None for f in template.fields)

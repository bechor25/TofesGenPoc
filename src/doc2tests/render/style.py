"""Shared, professional RTL document styling for rendered HTML (filled + blank)."""
from __future__ import annotations

from html import escape

BASE_CSS = """
:root{
  --ink:#1a2233; --muted:#6b7280; --line:#e6e8ee; --accent:#2b5cb8;
  --accent2:#3a6fd0; --bad:#c0342b; --bad-bg:#fdecea; --ok:#1f9d55;
  --bg:#eef1f6; --card:#ffffff;
}
*{box-sizing:border-box;}
body{
  margin:0; background:var(--bg); color:var(--ink); direction:rtl;
  font-family:'Assistant','Segoe UI','Helvetica Neue',Arial,sans-serif;
  padding:28px; line-height:1.5;
}
.doc{
  max-width:780px; margin:0 auto; background:var(--card);
  border:1px solid var(--line); border-radius:16px; overflow:hidden;
  box-shadow:0 10px 30px rgba(20,30,60,.08);
}
.doc__head{
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  color:#fff; padding:22px 28px;
}
.doc__title{margin:0; font-size:1.2rem; font-weight:700; letter-spacing:.01em;}
.doc__meta{margin-top:8px; font-size:.8rem; opacity:.95; display:flex; gap:8px;
  flex-wrap:wrap; align-items:center;}
.badge{display:inline-block; padding:3px 11px; border-radius:999px; font-size:.72rem;
  font-weight:600; background:rgba(255,255,255,.22); color:#fff;}
.badge--bad{background:var(--bad);}
.badge--ok{background:rgba(255,255,255,.28);}
table{border-collapse:collapse; width:100%;}
thead th{font-size:.7rem; letter-spacing:.04em; text-transform:uppercase;
  color:var(--muted); background:#fafbfd; text-align:right; padding:12px 28px;
  border-bottom:1px solid var(--line);}
tbody td{text-align:right; padding:13px 28px; border-bottom:1px solid var(--line);
  vertical-align:top;}
tbody tr:nth-child(even){background:#fafbfc;}
tbody tr:last-child td{border-bottom:none;}
.label{color:var(--muted); width:44%; font-weight:500;}
.value{font-weight:600; word-break:break-word;}
.value--invalid{color:var(--bad); background:var(--bad-bg); padding:2px 8px;
  border-radius:6px; display:inline-block;}
.ph{font-family:'SF Mono',Menlo,Consolas,'Courier New',monospace; font-size:.85rem;
  color:var(--accent); background:#eef3fb; padding:3px 9px; border-radius:7px;
  border:1px dashed #b9cdf0; display:inline-block; direction:ltr;}
.tag{font-size:.66rem; color:var(--muted); margin-inline-start:8px;
  border:1px solid var(--line); border-radius:5px; padding:1px 6px;}
.doc__foot{padding:13px 28px; font-size:.72rem; color:var(--muted);
  border-top:1px solid var(--line); background:#fcfcfd;}
"""


def html_shell(title: str, meta_html: str, rows_html: str, foot_html: str = "") -> str:
    return (
        '<!doctype html>\n<html lang="he" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title><style>{BASE_CSS}</style></head>"
        '<body><div class="doc"><div class="doc__head">'
        f'<h1 class="doc__title">{escape(title)}</h1>'
        f'<div class="doc__meta">{meta_html}</div></div>'
        "<table><thead><tr><th>שדה</th><th>ערך</th></tr></thead><tbody>"
        f"{rows_html}</tbody></table>"
        f'<div class="doc__foot">{foot_html}</div></div></body></html>'
    )

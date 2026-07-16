"""Map a raw log line to a human (Hebrew) pipeline stage for the live status.
Moved verbatim from the old Streamlit UI so the SSE stream shows the SAME real
stages the pipeline logs, scoped per run by the log marker."""
from __future__ import annotations

# ordered: first key found in a log line (scanned newest-first) wins.
STATUS_MAP: list[tuple[str, str]] = [
    ("editing image", "יוצר תמונה ב-gpt-image-2"),
    ("edit |", "יוצר תמונה ב-gpt-image-2"),
    ("rasteriz", "ממיר קובץ לתמונה"),
    ("transcribe", "מתעתק כל טקסט מהמסמך"),
    ("structure", "מבין ומבנה שדות"),
    ("understand", "מבין את מהות המסמך"),
    ("detect:", "מסווג ומחליט מה אישי"),
    ("data agent", "כותב ערכי תיאור ריאליסטיים"),
    ("shared into slots", "מקשר ערכים חוזרים"),
    ("generated", "מייצר דאטה מאומת"),
]


def friendly_stage(lines: list[str]) -> str:
    """Latest recognizable stage from these log lines (newest-first). '' if none."""
    for line in reversed(lines):
        msg = line.split("|", 1)[-1].strip().lower()
        for key, heb in STATUS_MAP:
            if key in msg:
                return heb
    return ""

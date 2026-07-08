from __future__ import annotations

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from doc2tests.contracts.records import Record
from doc2tests.contracts.template import CanonicalTemplate


def render_docx(template: CanonicalTemplate, record: Record, path: str) -> None:
    doc = Document()
    heading = doc.add_heading(template.doc_type, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    meta = doc.add_paragraph(
        f"record #{record.index} · {record.test_class}"
        + ("" if record.expected_valid else f" · expected INVALID ({record.violates})")
    )
    meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "שדה"
    hdr[1].text = "ערך"
    for f in template.fields:
        v = record.values.get(f.id)
        cells = table.add_row().cells
        cells[0].text = f.label
        cells[1].text = v.value if v else ""
    doc.save(path)

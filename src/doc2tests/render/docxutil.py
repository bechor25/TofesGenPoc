from __future__ import annotations

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


def set_rtl(paragraph: Paragraph) -> None:
    """Mark a paragraph right-to-left and right-aligned (Word bidi)."""
    p_pr = paragraph._p.get_or_add_pPr()
    p_pr.append(p_pr.makeelement(qn("w:bidi"), {}))
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

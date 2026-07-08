"""Real word coordinates: Tesseract for images (heb+eng), PyMuPDF for digital
PDFs. All boxes normalized to 0..1 of the page/image. These anchor the exact
overlay — the printed labels localize reliably even when values are handwritten."""
from __future__ import annotations

from dataclasses import dataclass

from doc2tests.ingest.loaders import detect_kind


@dataclass
class WordBox:
    text: str
    x: float  # left, 0..1
    y: float  # top, 0..1
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def image_word_boxes(path: str, lang: str = "heb+eng") -> list[WordBox]:
    import pytesseract
    from PIL import Image

    with Image.open(path) as img:
        iw, ih = img.size
        data = pytesseract.image_to_data(img, lang=lang,
                                         output_type=pytesseract.Output.DICT)
    boxes: list[WordBox] = []
    for i, text in enumerate(data["text"]):
        if not text.strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf < 30:  # drop low-confidence noise
            continue
        boxes.append(WordBox(
            text=text.strip(),
            x=data["left"][i] / iw, y=data["top"][i] / ih,
            w=data["width"][i] / iw, h=data["height"][i] / ih,
        ))
    return boxes


def pdf_word_boxes(path: str) -> list[WordBox]:
    import fitz

    boxes: list[WordBox] = []
    with fitz.open(path) as doc:
        if doc.page_count == 0:
            return boxes
        page = doc[0]
        pw, ph = page.rect.width, page.rect.height
        if pw == 0 or ph == 0:
            return boxes
        for x0, y0, x1, y1, word, *_ in page.get_text("words"):
            if not str(word).strip():
                continue
            boxes.append(WordBox(text=str(word).strip(),
                                 x=x0 / pw, y=y0 / ph,
                                 w=(x1 - x0) / pw, h=(y1 - y0) / ph))
    return boxes


def word_boxes(path: str) -> list[WordBox]:
    """Route by format. Digital PDFs use their text layer; scanned PDFs and
    images fall back to Tesseract; Word documents have no visual layout here."""
    kind = detect_kind(path)
    if kind == "pdf":
        boxes = pdf_word_boxes(path)
        if boxes:
            return boxes
        # scanned PDF with no text layer -> render page 1 and OCR it
        import tempfile

        from doc2tests.ingest.loaders import load_images
        images = load_images(path)
        if not images:
            return []
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(images[0])
            tmp_path = tmp.name
        return image_word_boxes(tmp_path)
    if kind == "image":
        return image_word_boxes(path)
    return []  # docx: no coordinate layer


def group_lines(boxes: list[WordBox], y_tol: float = 0.012) -> list[list[WordBox]]:
    """Cluster words into visual lines by vertical proximity, ordered top->bottom,
    each line ordered right->left (RTL)."""
    lines: list[list[WordBox]] = []
    for box in sorted(boxes, key=lambda b: b.cy):
        placed = False
        for line in lines:
            if abs(line[0].cy - box.cy) <= y_tol:
                line.append(box)
                placed = True
                break
        if not placed:
            lines.append([box])
    for line in lines:
        line.sort(key=lambda b: b.x, reverse=True)  # RTL
    return lines

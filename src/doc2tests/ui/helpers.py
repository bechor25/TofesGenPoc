from __future__ import annotations

import io
import zipfile

from doc2tests.contracts.records import Record


def zip_images(images: list[bytes], prefix: str = "form") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, img in enumerate(images, start=1):
            zf.writestr(f"{prefix}_{i}.png", img)
    return buf.getvalue()


def records_to_rows(records: list[Record]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for r in records:
        row: dict[str, object] = {"#": r.index + 1}
        for fid, v in r.values.items():
            row[fid] = v.value
        rows.append(row)
    return rows

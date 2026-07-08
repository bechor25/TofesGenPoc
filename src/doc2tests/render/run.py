from __future__ import annotations

import os
from typing import Any

from doc2tests.contracts.state import GraphState, RenderedDoc
from doc2tests.render.docx import render_docx
from doc2tests.render.html import render_html


def render_fill(state: GraphState, out_dir: str) -> dict[str, Any]:
    if state.template is None or not state.population:
        return {"outputs": []}
    os.makedirs(out_dir, exist_ok=True)
    outputs: list[RenderedDoc] = []
    for record in state.population:
        for fmt in state.config.formats:
            path = os.path.join(out_dir, f"record_{record.index:04d}.{fmt}")
            if fmt == "html":
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(render_html(state.template, record))
            elif fmt == "docx":
                render_docx(state.template, record, path)
            else:
                continue
            outputs.append(RenderedDoc(record_index=record.index, fmt=fmt, path=path))
    return {"outputs": outputs}

"""Label-anchored placement: match each field's (printed) label to real OCR word
boxes, then place the value region relative to that label. Printed labels localize
reliably, so this works even when the value itself is handwritten."""
from __future__ import annotations

import re
from typing import Any

from doc2tests.contracts.enums import RenderStrategy
from doc2tests.contracts.state import GraphState
from doc2tests.contracts.template import BBox
from doc2tests.ingest.ocr_boxes import WordBox, group_lines, word_boxes

_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)  # letters only (any script)

_MAX_VALUE_W = 0.35
_MIN_GAP = 0.03


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t}


def _span(words: list[WordBox]) -> tuple[float, float, float, float]:
    left = min(w.x for w in words)
    top = min(w.y for w in words)
    right = max(w.x + w.w for w in words)
    bottom = max(w.y + w.h for w in words)
    return left, top, right, bottom


def anchor_field_bbox(label: str, lines: list[list[WordBox]]) -> BBox | None:
    label_tokens = _tokens(label)
    if not label_tokens:
        return None

    best: tuple[float, list[WordBox]] | None = None
    for line in lines:
        matched = [w for w in line if _tokens(w.text) & label_tokens]
        if not matched:
            continue
        score = len(matched) / len(label_tokens)
        if best is None or score > best[0]:
            best = (score, matched)
    if best is None or best[0] < 0.5:
        return None

    left, top, right, bottom = _span(best[1])
    height = max(bottom - top, 0.012)
    left_gap, right_gap = left, 1.0 - right
    if left_gap >= right_gap and left_gap > _MIN_GAP:      # value to the left (RTL)
        vw = min(_MAX_VALUE_W, left_gap)
        vx = max(0.0, left - vw)
    elif right_gap > _MIN_GAP:                              # value to the right
        vw = min(_MAX_VALUE_W, right_gap)
        vx = right
    else:
        return None
    return BBox(page=1, x=round(vx, 4), y=round(top, 4),
               w=round(vw, 4), h=round(height, 4))


def anchor_fields(state: GraphState) -> dict[str, Any]:
    """Node: replace fabricated bboxes with label-anchored real coordinates."""
    if state.template is None:
        return {}
    try:
        boxes = word_boxes(state.input_ref.path)
    except Exception:  # noqa: BLE001 - OCR failure must not break the pipeline
        boxes = []
    if not boxes:
        return {}
    lines = group_lines(boxes)
    new_fields = []
    for f in state.template.fields:
        bb = anchor_field_bbox(f.label, lines)
        new_fields.append(f.model_copy(update={"bbox": bb}) if bb else f)

    strategy = (RenderStrategy.overlay if any(f.bbox for f in new_fields)
                else state.template.source.render_strategy)
    new_source = state.template.source.model_copy(update={"render_strategy": strategy})
    return {"template": state.template.model_copy(
        update={"fields": new_fields, "source": new_source})}

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from doc2tests.common.logging import get_logger
from doc2tests.contracts.state import GraphState, StageError
from doc2tests.coverage.report import build_coverage
from doc2tests.deid.detect import detect_fields
from doc2tests.generate.population import generate_population
from doc2tests.ingest.loaders import detect_kind, load_images
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMProvider
from doc2tests.render.layout import deidentify_layout, generate_layout_template
from doc2tests.render.run import render_fill
from doc2tests.schema.infer import extract_schema
from doc2tests.template.anchor import anchor_fields
from doc2tests.template.build import build_template

_log = get_logger("graph")


def review_gate(state: GraphState) -> dict[str, Any]:
    """Human-in-the-loop checkpoint. Applies any label edits captured in
    state.review before generation. Execution pauses *before* this node."""
    if state.review and state.review.edits and state.template is not None:
        edits = state.review.edits
        fields = [f.model_copy(update={"label": edits.get(f.id, f.label)})
                  for f in state.template.fields]
        return {"template": state.template.model_copy(update={"fields": fields})}
    return {}


def _coverage_node(state: GraphState) -> dict[str, Any]:
    if state.template is None:
        return {}
    return {"coverage": build_coverage(state.template, state.population)}


def _build_layout_node(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    """Recreate the source document as a fillable, de-identified HTML template
    (skipped for Word inputs)."""
    if state.template is None or detect_kind(state.input_ref.path) == "docx":
        return {}
    try:
        images = load_images(state.input_ref.path)
        html = generate_layout_template(images, state.template.fields, provider)
        value_by_id = {tf.id: df.value for tf, df in
                       zip(state.template.fields, state.detected_fields, strict=False)}
        html = deidentify_layout(html, value_by_id)
        n_pii = sum(1 for v in value_by_id.values() if v.strip())
        _log.info("recreated layout (%d chars), de-identified %d detected values",
                  len(html), n_pii)
    except Exception as exc:  # noqa: BLE001 - layout is best-effort, never fatal
        _log.exception("build_layout failed")
        return {"errors": [StageError(stage="build_layout", message=str(exc))]}
    return {"layout_html": html}


def build_graph(vision_provider: LLMProvider, out_dir: str) -> Any:
    """Compile the F1..F6 workflow with a human review gate before generation.

    interrupt_before=["review_gate"] pauses the run once the canonical template
    exists, so a person can inspect/edit it, then resume to generate + render.
    """
    g = StateGraph(GraphState)

    g.add_node("ingest_parse", lambda s: ingest_parse(s, vision_provider))
    g.add_node("detect_fields", detect_fields)
    g.add_node("build_template", build_template)
    g.add_node("anchor_fields", anchor_fields)
    g.add_node("extract_schema", extract_schema)
    g.add_node("build_layout", lambda s: _build_layout_node(s, vision_provider))
    g.add_node("review_gate", review_gate)
    g.add_node("generate_population", generate_population)
    g.add_node("coverage", _coverage_node)
    g.add_node("render_fill", lambda s: render_fill(s, out_dir))

    g.add_edge(START, "ingest_parse")
    g.add_edge("ingest_parse", "detect_fields")
    g.add_edge("detect_fields", "build_template")
    g.add_edge("build_template", "anchor_fields")
    g.add_edge("anchor_fields", "extract_schema")
    g.add_edge("extract_schema", "build_layout")
    g.add_edge("build_layout", "review_gate")
    g.add_edge("review_gate", "generate_population")
    g.add_edge("generate_population", "coverage")
    g.add_edge("coverage", "render_fill")
    g.add_edge("render_fill", END)

    return g.compile(checkpointer=MemorySaver(), interrupt_before=["review_gate"])

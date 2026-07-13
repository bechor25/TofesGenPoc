from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from doc2tests.common.logging import get_logger
from doc2tests.contracts.state import GraphState, StageError
from doc2tests.deid.detect import detect_fields
from doc2tests.generate.population import generate_population
from doc2tests.imagegen.edit import Replacement, edit_form_image
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMProvider

_log = get_logger("graph")


def review_gate(state: GraphState) -> dict[str, Any]:
    """Human-in-the-loop checkpoint. The UI captures the final reviewed values in
    state.review.values; they replace machine detection. Execution pauses BEFORE
    this node (interrupt_before)."""
    if state.review and state.review.values:
        return {"detected": state.review.values}
    return {}


def _edit_images_node(state: GraphState, provider: LLMProvider) -> dict[str, Any]:
    if not state.page_images or not state.population:
        return {}
    original = state.page_images[0]
    personal = [d for d in state.detected if d.is_personal]
    outputs: list[bytes] = []
    errors: list[StageError] = []
    for rec in state.population:
        reps = [Replacement(old=d.value, new=rec.values[d.id].value)
                for d in personal if d.id in rec.values]
        try:
            outputs.append(edit_form_image(original, reps, provider))
        except Exception as exc:  # noqa: BLE001 - per-image failure is non-fatal
            _log.exception("edit failed for record %d", rec.index)
            errors.append(StageError(stage="edit_images", message=str(exc)))
    _log.info("produced %d edited image(s)", len(outputs))
    return {"output_images": outputs, "errors": errors}


def build_graph(provider: LLMProvider) -> Any:
    """Compile the pivot workflow with a human review gate before generation.

    interrupt_before=["review_gate"] pauses once values are detected, so a person
    can confirm/add/edit them, then resume to generate + edit images.
    """
    g = StateGraph(GraphState)
    g.add_node("ingest_parse", lambda s: ingest_parse(s, provider))
    g.add_node("detect_fields", detect_fields)
    g.add_node("review_gate", review_gate)
    g.add_node("generate_population", generate_population)
    g.add_node("edit_images", lambda s: _edit_images_node(s, provider))

    g.add_edge(START, "ingest_parse")
    g.add_edge("ingest_parse", "detect_fields")
    g.add_edge("detect_fields", "review_gate")
    g.add_edge("review_gate", "generate_population")
    g.add_edge("generate_population", "edit_images")
    g.add_edge("edit_images", END)

    return g.compile(checkpointer=MemorySaver(), interrupt_before=["review_gate"])

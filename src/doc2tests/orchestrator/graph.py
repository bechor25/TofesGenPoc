from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from doc2tests.common.logging import get_logger
from doc2tests.contracts.state import GraphState
from doc2tests.deid.detect import detect_fields
from doc2tests.generate.population import generate_population
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


def build_graph(extract_provider: LLMProvider) -> Any:
    """Compile the DATA pipeline with a human review gate. Image rendering is a
    SEPARATE, on-demand step (``imagegen.edit`` / ``batch.render_variant``) the caller
    meters — the graph NEVER renders images. So picking N generates only validated data,
    and the user reviews/approves it before any expensive image is produced.

    extract_provider runs the grounded extraction (OpenAI gpt-5.1).
    interrupt_before=["review_gate"] pauses once values are detected, so a person can
    confirm/add/edit them, then resume to generate the data variants.
    """
    g = StateGraph(GraphState)
    g.add_node("ingest_parse", lambda s: ingest_parse(s, extract_provider))
    g.add_node("detect_fields", detect_fields)
    g.add_node("review_gate", review_gate)
    g.add_node("generate_population", generate_population)

    g.add_edge(START, "ingest_parse")
    g.add_edge("ingest_parse", "detect_fields")
    g.add_edge("detect_fields", "review_gate")
    g.add_edge("review_gate", "generate_population")
    g.add_edge("generate_population", END)

    return g.compile(checkpointer=MemorySaver(), interrupt_before=["review_gate"])

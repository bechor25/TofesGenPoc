import os

import pytest

from doc2tests.contracts.batch import DocumentResult
from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.records import Record
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.orchestrator.batch import render_variant
from doc2tests.orchestrator.config import build_extract_provider, build_image_provider
from doc2tests.orchestrator.graph import build_graph

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY"
)


def test_live_data_graph_then_on_demand_render():
    graph = build_graph(build_extract_provider())
    config = {"configurable": {"thread_id": "live-e2e"}}
    state = GraphState(
        input_ref=InputRef(path="tests/fixtures/doc2_printed_tax_letter.jpeg",
                           kind=SourceKind.image),
        config=RunConfig(n=2, seed=5),
    )
    # phase 1: extract -> pause at review gate
    graph.invoke(state, config)
    snap = graph.get_state(config)
    assert snap.next == ("review_gate",)
    detected = snap.values["detected"]
    assert len(detected) >= 3

    # phase 2: approve detected values -> generate DATA only (no images from the graph)
    graph.update_state(config, {"review": {"approved": True, "values": detected}})
    final = graph.invoke(None, config)
    assert len(final["population"]) == 2
    assert not final.get("output_images")

    # phase 3: render ONE variant on demand — the expensive, metered step is separate
    snap = graph.get_state(config)
    doc = DocumentResult(
        path="live",
        detected=snap.values["detected"],
        population=[p if isinstance(p, Record) else Record(**p)
                    for p in final["population"]],
        page_image=snap.values["page_images"][0],
    )
    img = render_variant(doc, 0, build_image_provider())
    assert img[:4] == b"\x89PNG" or img[:3] == b"\xff\xd8\xff"  # PNG or JPEG

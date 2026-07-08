import os

import pytest

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.orchestrator.config import build_vision_provider
from doc2tests.orchestrator.graph import build_graph

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY"
)


def test_live_full_pipeline_produces_documents(tmp_path):
    graph = build_graph(build_vision_provider(), str(tmp_path / "out"))
    config = {"configurable": {"thread_id": "live-e2e"}}
    state = GraphState(
        input_ref=InputRef(path="tests/fixtures/doc2_printed_tax_letter.jpeg",
                           kind=SourceKind.image),
        config=RunConfig(n=8, seed=5, formats=["html", "docx"]),
    )
    # phase 1: extract -> pause at review gate
    graph.invoke(state, config)
    snap = graph.get_state(config)
    assert snap.next == ("review_gate",)
    assert snap.values["template"] is not None
    assert len(snap.values["template"].fields) >= 3

    # phase 2: approve -> generate + render
    graph.update_state(config, {"review": {"approved": True, "edits": {}}})
    final = graph.invoke(None, config)
    assert len(final["population"]) == 8
    assert final["coverage"] is not None
    assert final["outputs"]
    # every rendered file actually exists on disk
    for doc in final["outputs"]:
        assert os.path.exists(doc.path)

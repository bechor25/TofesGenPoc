import json

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.orchestrator.graph import build_graph
from doc2tests.providers.base import LLMResponse


class _FakeVision:
    name = "fake-vision"

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("vision only")

    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text=json.dumps({
            "raw_text": "טופס",
            "fields": [
                {"label": "מספר זהות", "value": "123456782", "value_kind": "handwritten"},
                {"label": "תאריך חתימת חוזה", "value": "2019", "value_kind": "handwritten"},
                {"label": "תאריך כניסה", "value": "31.10.21", "value_kind": "handwritten"},
            ],
        }))


def _state(tmp_path):
    img = tmp_path / "f.jpeg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    return GraphState(
        input_ref=InputRef(path=str(img), kind=SourceKind.image),
        config=RunConfig(n=12, seed=3, formats=["html"]),
    )


def test_graph_interrupts_at_review_then_resumes(tmp_path):
    graph = build_graph(_FakeVision(), str(tmp_path / "out"))
    config = {"configurable": {"thread_id": "t1"}}

    # phase 1: run to the review gate
    graph.invoke(_state(tmp_path), config)
    snap = graph.get_state(config)
    assert snap.next == ("review_gate",)            # paused before review
    assert snap.values["template"] is not None
    assert len(snap.values["template"].fields) == 3
    assert snap.values["population"] == []          # not generated yet

    # phase 2: approve + resume to completion
    graph.update_state(config, {"review": {"approved": True, "edits": {}}})
    final = graph.invoke(None, config)
    assert len(final["population"]) == 12
    assert final["coverage"] is not None
    assert final["outputs"] and final["outputs"][0].fmt == "html"


def test_graph_applies_review_edits(tmp_path):
    graph = build_graph(_FakeVision(), str(tmp_path / "out2"))
    config = {"configurable": {"thread_id": "t2"}}
    graph.invoke(_state(tmp_path), config)
    snap = graph.get_state(config)
    first_id = snap.values["template"].fields[0].id

    graph.update_state(config, {"review": {"approved": True,
                                           "edits": {first_id: "תווית ערוכה"}}})
    final = graph.invoke(None, config)
    edited = next(f for f in final["template"].fields if f.id == first_id)
    assert edited.label == "תווית ערוכה"

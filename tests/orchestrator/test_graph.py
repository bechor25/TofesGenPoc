from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import DetectedValue, GraphState, InputRef, ReviewDecision
from doc2tests.orchestrator.graph import build_graph
from doc2tests.providers.base import LLMResponse


class _StubProvider:
    name = "stub"

    def complete_text(self, *a, **k):
        return LLMResponse(text="{}")

    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text='{"raw_text":"t","fields":['
                                '{"label":"מספר זהות","value":"123456789"}]}')

    def edit_image(self, image, prompt, **k):
        return b"EDITED:" + image


def test_graph_runs_end_to_end_with_review(monkeypatch):
    monkeypatch.setattr("doc2tests.ingest.parse.rasterize", lambda p: [b"IMG"])
    stub = _StubProvider()
    app = build_graph(stub)
    cfg = {"configurable": {"thread_id": "t1"}}
    init = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))

    # run up to the interrupt before review_gate
    app.invoke(init, cfg)
    snap = app.get_state(cfg)
    detected = snap.values["detected"]
    assert detected and detected[0].field_type.value == "israeli_id"
    assert isinstance(detected[0], DetectedValue)

    # user approves the detected values -> graph generates DATA only
    app.update_state(cfg, {"review": ReviewDecision(approved=True, values=detected)})
    final = app.invoke(None, cfg)
    assert len(final["population"]) == final["config"].n
    # image rendering is a SEPARATE on-demand step — the graph must NOT render images
    assert not final.get("output_images")

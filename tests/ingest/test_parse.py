from unittest.mock import patch

from doc2tests.contracts.enums import SourceKind, ValueKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMResponse


class _FakeProvider:
    name = "fake"

    def __init__(self, text: str):
        self._text = text
        self.saw_images = None

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("ingest must use vision")

    def extract_vision(self, images, prompt, *, json_mode=False):
        self.saw_images = images
        return LLMResponse(text=self._text)

    def edit_image(self, image, prompt, **k):
        return b""


def _state() -> GraphState:
    return GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))


def test_ingest_parse_rasterizes_then_extracts():
    provider = _FakeProvider(
        '{"raw_text":"t","fields":['
        '{"label":"מספר זהות","value":"123456782","value_kind":"handwritten"}]}')
    with patch("doc2tests.ingest.parse.rasterize", return_value=[b"\x89PNG..."]):
        out = ingest_parse(_state(), provider)
    assert out["page_images"] == [b"\x89PNG..."]
    pr = out["parse_result"]
    assert pr.provider == "fake"
    assert pr.fields[0].value == "123456782"
    assert pr.fields[0].value_kind == ValueKind.handwritten
    assert provider.saw_images == [b"\x89PNG..."]


def test_ingest_parse_records_error_on_bad_json():
    provider = _FakeProvider("the model refused")
    with patch("doc2tests.ingest.parse.rasterize", return_value=[b"IMG"]):
        out = ingest_parse(_state(), provider)
    assert out["parse_result"].fields == []
    assert out["errors"][0].stage == "ingest_parse"

import json

from doc2tests.contracts.enums import SourceKind, ValueKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMResponse


class _FakeProvider:
    name = "fake"

    def __init__(self, payload: dict):
        self._payload = payload
        self.saw_images = None

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("F1 must use vision")

    def extract_vision(self, images, prompt, *, json_mode=False):
        self.saw_images = images
        return LLMResponse(text=json.dumps(self._payload))


def _state(tmp_path) -> GraphState:
    img = tmp_path / "d.jpeg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    return GraphState(input_ref=InputRef(path=str(img), kind=SourceKind.image))


def test_parse_populates_fields(tmp_path):
    provider = _FakeProvider({
        "raw_text": "בקשה",
        "fields": [
            {"label": "מספר זהות", "value": "123456782", "value_kind": "handwritten"},
            {"label": "תאריך כניסה", "value": "31.10.21", "value_kind": "printed"},
        ],
    })
    out = ingest_parse(_state(tmp_path), provider)
    pr = out["parse_result"]
    assert pr.provider == "fake"
    assert len(pr.fields) == 2
    assert pr.fields[0].value == "123456782"
    assert pr.fields[0].value_kind == ValueKind.handwritten
    assert provider.saw_images and isinstance(provider.saw_images[0], bytes)


def test_parse_records_error_on_bad_json(tmp_path):
    class _Bad(_FakeProvider):
        def extract_vision(self, images, prompt, *, json_mode=False):
            return LLMResponse(text="the model refused")

    out = ingest_parse(_state(tmp_path), _Bad({}))
    assert out["parse_result"].fields == []
    assert out["errors"][0].stage == "ingest_parse"


def test_word_document_uses_text_extraction(tmp_path):
    from docx import Document

    from doc2tests.contracts.enums import SourceKind
    from doc2tests.contracts.state import InputRef

    path = tmp_path / "form.docx"
    doc = Document()
    doc.add_paragraph("מספר זהות: 123456782")
    doc.save(str(path))

    class _TextProvider:
        name = "text-fake"

        def __init__(self):
            self.saw_text = None

        def extract_vision(self, images, prompt, *, json_mode=False):
            raise AssertionError("docx must use text extraction, not vision")

        def complete_text(self, prompt, *, system=None, json_mode=False):
            self.saw_text = prompt
            return LLMResponse(text=json.dumps(
                {"raw_text": "x", "fields": [
                    {"label": "מספר זהות", "value": "123456782", "value_kind": "printed"}]}))

    provider = _TextProvider()
    state = GraphState(input_ref=InputRef(path=str(path), kind=SourceKind.docx))
    out = ingest_parse(state, provider)
    assert out["parse_result"].fields[0].value == "123456782"
    assert "123456782" in provider.saw_text  # docx text was fed into the prompt

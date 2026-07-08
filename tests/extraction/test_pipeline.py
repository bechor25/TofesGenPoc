import json

from doc2tests.contracts.enums import FieldType, RelationOp, SourceKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.deid.detect import detect_fields
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMResponse
from doc2tests.schema.infer import extract_schema
from doc2tests.template.build import build_template


class _FakeVision:
    name = "fake-vision"

    def __init__(self, payload):
        self._payload = payload

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("vision only")

    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text=json.dumps(self._payload))


def _apply(state, patch):
    return state.model_copy(update=patch)


def test_full_extraction_chain(tmp_path):
    img = tmp_path / "form.jpeg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    provider = _FakeVision({
        "raw_text": "בקשה להעברת תעודת זכאות",
        "fields": [
            {"label": "מספר זהות (מבקש ראשי)", "value": "123456782", "value_kind": "handwritten"},
            {"label": "תאריך חתימת חוזה", "value": "2019", "value_kind": "handwritten"},
            {"label": "תאריך כניסה לדירה", "value": "31.10.21", "value_kind": "handwritten"},
        ],
    })

    state = GraphState(input_ref=InputRef(path=str(img), kind=SourceKind.image))
    state = _apply(state, ingest_parse(state, provider))
    state = _apply(state, detect_fields(state))
    state = _apply(state, build_template(state))
    state = _apply(state, extract_schema(state))

    tmpl = state.template
    assert tmpl is not None
    ids = [f.id for f in tmpl.fields]
    assert len(ids) == len(set(ids)) == 3
    id_field = next(f for f in tmpl.fields if f.type == FieldType.israeli_id)
    assert id_field.constraints.checksum == "israeli_id"
    order_rels = [r for r in tmpl.relations if r.op == RelationOp.le]
    assert order_rels and {order_rels[0].left, order_rels[0].right} <= set(ids)
    assert state.errors == []

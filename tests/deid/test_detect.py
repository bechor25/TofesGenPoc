from doc2tests.contracts.enums import FieldType, SourceKind, ValueKind
from doc2tests.contracts.state import GraphState, InputRef, ParsedField, ParseResult
from doc2tests.deid.detect import detect_fields


def _state_with(parsed):
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        parse_result=ParseResult(fields=parsed, provider="fake"),
    )


def test_detect_maps_types_and_pii():
    st = _state_with([
        ParsedField(label="מספר זהות", value="123456782", value_kind=ValueKind.handwritten),
        ParsedField(label="הערות", value="טקסט"),
    ])
    out = detect_fields(st)
    detected = out["detected_fields"]
    assert detected[0].type == FieldType.israeli_id
    assert detected[0].pii is True
    assert detected[0].value_kind == ValueKind.handwritten
    assert detected[1].type == FieldType.free_text


def test_detect_empty_when_no_parse_result():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    out = detect_fields(st)
    assert out["detected_fields"] == []

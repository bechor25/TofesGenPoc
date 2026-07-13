from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import GraphState, InputRef, ParsedField, ParseResult
from doc2tests.deid.detect import detect_fields


def _state(fields):
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        parse_result=ParseResult(fields=fields),
    )


def test_detect_assigns_ids_types_and_personal_flag():
    st = _state([
        ParsedField(label="שם מלא", value="דנה כהן"),
        ParsedField(label="מספר זהות", value="123456782"),
        ParsedField(label="גוש", value="6941"),
    ])
    out = detect_fields(st)["detected"]
    by_label = {d.label: d for d in out}
    assert by_label["שם מלא"].field_type == FieldType.hebrew_name
    assert by_label["שם מלא"].is_personal is True
    assert by_label["מספר זהות"].field_type == FieldType.israeli_id
    assert by_label["מספר זהות"].is_personal is True
    assert by_label["גוש"].is_personal is False
    assert len({d.id for d in out}) == 3          # unique ids
    assert all(d.id for d in out)


def test_detect_passthrough_without_parse():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert detect_fields(st)["detected"] == []

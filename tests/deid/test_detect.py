from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import GraphState, InputRef, ParsedField, ParseResult
from doc2tests.deid.detect import detect_fields


def _state(fields):
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        parse_result=ParseResult(fields=fields),
    )


def test_detect_assigns_ids_and_types():
    st = _state([
        ParsedField(label="שם מלא", value="דנה כהן"),
        ParsedField(label="מספר זהות", value="123456782"),
        ParsedField(label="כתובת", value="הרצל 5 חיפה"),
    ])
    out = detect_fields(st)["detected"]
    by_label = {d.label: d for d in out}
    assert by_label["שם מלא"].field_type == FieldType.hebrew_name
    assert by_label["מספר זהות"].field_type == FieldType.israeli_id
    assert by_label["כתובת"].field_type == FieldType.address
    assert len({d.id for d in out}) == 3          # unique ids


def test_every_filled_value_is_personal():
    # not just names/ids: dates, addresses, numbers, free text — anything with a
    # value is case-specific and must be replaced.
    st = _state([
        ParsedField(label="תאריך", value="28/07/2019"),
        ParsedField(label="גוש", value="6941"),
        ParsedField(label="הערות", value="בקשה כללית"),
        ParsedField(label="מספר שומה", value="119128627"),
    ])
    out = detect_fields(st)["detected"]
    assert all(d.is_personal for d in out)


def test_empty_value_is_not_personal():
    # a labelled-but-blank field has nothing to replace
    st = _state([ParsedField(label="רשות המסים", value="")])
    out = detect_fields(st)["detected"]
    assert out[0].is_personal is False


def test_detect_passthrough_without_parse():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert detect_fields(st)["detected"] == []

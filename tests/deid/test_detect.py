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


def test_model_type_overrides_label_classifier():
    # DYNAMIC typing: the model judged this recipient value to be an address by content,
    # even though the label "נמען" would make the keyword classifier call it a name.
    # The model's type must win, so the address generator runs.
    st = _state([
        ParsedField(label="נמען", value="הרצל 5 חיפה", field_type=FieldType.address),
    ])
    out = detect_fields(st)["detected"]
    assert out[0].field_type == FieldType.address


def test_falls_back_to_classifier_when_model_gives_no_type():
    # no model type -> the value-shape / label classifier decides (fallback path intact)
    st = _state([ParsedField(label="מספר זהות", value="123456782", field_type=None)])
    out = detect_fields(st)["detected"]
    assert out[0].field_type == FieldType.israeli_id


def test_extractor_personal_flag_drives_replacement():
    # the extractor tags person/case data personal=True and static form content False
    st = _state([
        ParsedField(label="שם הרוכש", value="דנה כהן", personal=True),
        ParsedField(label="אבחנה", value="קרע בכתף ימין", personal=True),
        ParsedField(label="רשות המסים", value="רשות המסים בישראל", personal=False),
        ParsedField(label="טלפון משרד", value="04-6327888", personal=False),
    ])
    out = {d.label: d for d in detect_fields(st)["detected"]}
    assert out["שם הרוכש"].is_personal is True
    assert out["אבחנה"].is_personal is True
    assert out["רשות המסים"].is_personal is False       # static scaffolding kept
    assert out["טלפון משרד"].is_personal is False


def test_empty_value_is_not_personal():
    # a personal-tagged but blank field has nothing to replace
    st = _state([ParsedField(label="שם", value="", personal=True)])
    out = detect_fields(st)["detected"]
    assert out[0].is_personal is False


def test_detect_passthrough_without_parse():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert detect_fields(st)["detected"] == []

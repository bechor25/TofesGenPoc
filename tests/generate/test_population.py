from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import DetectedValue, GraphState, InputRef, RunConfig
from doc2tests.generate.population import generate_population
from doc2tests.validators import validate


def _state(n):
    detected = [
        DetectedValue(id="pid", label="ת.ז", value="123456782",
                      field_type=FieldType.israeli_id, is_personal=True),
        DetectedValue(id="nm", label="שם", value="דנה כהן",
                      field_type=FieldType.hebrew_name, is_personal=True),
        DetectedValue(id="city", label="עיר", value="חיפה",
                      field_type=FieldType.free_text, is_personal=False),
    ]
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        detected=detected, config=RunConfig(n=n, seed=7),
    )


def test_population_has_exactly_n_records():
    out = generate_population(_state(10))["population"]
    assert len(out) == 10


def test_only_personal_fields_are_generated():
    rec = generate_population(_state(5))["population"][0]
    assert set(rec.values) == {"pid", "nm"}     # city (non-personal) not generated


def test_generated_values_are_valid():
    for rec in generate_population(_state(8))["population"]:
        assert validate(FieldType.israeli_id, rec.values["pid"].value) is True
        assert rec.values["pid"].valid is True


def test_deterministic_same_seed():
    a = generate_population(_state(6))["population"]
    b = generate_population(_state(6))["population"]
    assert [r.values["pid"].value for r in a] == [r.values["pid"].value for r in b]


def test_passthrough_without_detected():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert generate_population(st)["population"] == []

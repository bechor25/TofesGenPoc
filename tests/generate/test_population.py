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


def _coherence_state():
    # a recipient address line printed twice (same slot) + a different line (other slot)
    detected = [
        DetectedValue(id="a1", label="נמען שורה 1", value="הרצל 5",
                      field_type=FieldType.address, is_personal=True, slot="recip_l1"),
        DetectedValue(id="a1r", label="נמען שורה 1 (חוזר)", value="הרצל 5",
                      field_type=FieldType.address, is_personal=True, slot="recip_l1"),
        DetectedValue(id="a2", label="נמען שורה 2", value="חיפה",
                      field_type=FieldType.address, is_personal=True, slot="recip_l2"),
    ]
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        detected=detected, config=RunConfig(n=5, seed=7),
    )


def test_same_slot_shares_one_value_across_the_form():
    # the repeated recipient line must get the IDENTICAL generated value (coherence)
    for rec in generate_population(_coherence_state())["population"]:
        assert rec.values["a1"].value == rec.values["a1r"].value
        # a different slot (line 2) is its own value, not tied to line 1
        assert rec.values["a2"].value != rec.values["a1"].value

from doc2tests.contracts.enums import FieldType, RelationOp, SourceKind, TestClass
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.contracts.template import (
    CanonicalTemplate,
    DocSource,
    Field,
    Relation,
)
from doc2tests.generate.population import generate_population
from doc2tests.validators import is_valid_israeli_id


def _state(n):
    tmpl = CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[
            Field(id="pid", label="מספר זהות", type=FieldType.israeli_id),
            Field(id="a", label="חוזה", type=FieldType.date),
            Field(id="b", label="כניסה", type=FieldType.date),
        ],
        relations=[Relation(kind="order", op=RelationOp.le, left="a", right="b")],
    )
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        template=tmpl, config=RunConfig(n=n, seed=7),
    )


def test_population_has_exactly_n_records():
    out = generate_population(_state(20))
    assert len(out["population"]) == 20


def test_population_covers_all_three_classes():
    pop = generate_population(_state(50))["population"]
    classes = {r.test_class for r in pop}
    assert classes == {TestClass.equivalence, TestClass.boundary, TestClass.negative}


def test_equivalence_records_have_valid_ids():
    pop = generate_population(_state(50))["population"]
    for r in pop:
        if r.test_class == TestClass.equivalence:
            assert is_valid_israeli_id(r.values["pid"].value)
            assert r.expected_valid is True


def test_negative_records_are_flagged():
    pop = generate_population(_state(50))["population"]
    negs = [r for r in pop if r.test_class == TestClass.negative]
    assert negs
    for r in negs:
        assert r.expected_valid is False
        assert r.violates


def test_deterministic_same_seed():
    a = generate_population(_state(10))["population"]
    b = generate_population(_state(10))["population"]
    assert [r.values["pid"].value for r in a] == [r.values["pid"].value for r in b]


def test_passthrough_without_template():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert generate_population(st)["population"] == []

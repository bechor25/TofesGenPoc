from doc2tests.contracts.enums import FieldType, RelationOp, SourceKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.contracts.template import (
    CanonicalTemplate,
    DocSource,
    Field,
)
from doc2tests.schema.infer import extract_schema


def _state_with_template(fields):
    tmpl = CanonicalTemplate(
        doc_type="d",
        source=DocSource(kind=SourceKind.image),
        fields=fields,
    )
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        template=tmpl,
    )


def test_adds_order_relation_between_two_dates():
    st = _state_with_template([
        Field(id="contract_date", label="תאריך חתימת חוזה", type=FieldType.date),
        Field(id="entry_date", label="תאריך כניסה לדירה", type=FieldType.date),
    ])
    out = extract_schema(st)
    tmpl = out["template"]
    rels = [r for r in tmpl.relations if r.kind == "order"]
    assert len(rels) == 1
    assert rels[0].op == RelationOp.le
    assert {rels[0].left, rels[0].right} == {"contract_date", "entry_date"}


def test_schema_notes_cover_every_field():
    st = _state_with_template([
        Field(id="a_id", label="מספר זהות", type=FieldType.israeli_id),
    ])
    out = extract_schema(st)
    assert "a_id" in out["field_schema"].notes


def test_no_relation_with_single_date():
    st = _state_with_template([
        Field(id="only_date", label="תאריך", type=FieldType.date),
    ])
    out = extract_schema(st)
    assert [r for r in out["template"].relations if r.kind == "order"] == []


def test_passthrough_when_no_template():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    out = extract_schema(st)
    assert out["template"] is None

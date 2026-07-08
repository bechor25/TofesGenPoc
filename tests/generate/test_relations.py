from doc2tests.contracts.enums import FieldType, RelationOp, SourceKind
from doc2tests.contracts.template import (
    CanonicalTemplate,
    DocSource,
    Field,
    Relation,
)
from doc2tests.generate.relations import satisfies_order, violate_order


def _tmpl():
    return CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="a", label="חוזה", type=FieldType.date),
                Field(id="b", label="כניסה", type=FieldType.date)],
        relations=[Relation(kind="order", op=RelationOp.le, left="a", right="b")],
    )


def test_satisfies_order_true_when_ordered():
    assert satisfies_order(_tmpl(), {"a": "01.01.2020", "b": "01.02.2020"}) is True


def test_satisfies_order_false_when_reversed():
    assert satisfies_order(_tmpl(), {"a": "01.03.2020", "b": "01.01.2020"}) is False


def test_violate_order_swaps_to_break_relation():
    values = {"a": "01.01.2020", "b": "01.02.2020"}
    broken = violate_order(_tmpl(), values)
    assert satisfies_order(_tmpl(), broken) is False

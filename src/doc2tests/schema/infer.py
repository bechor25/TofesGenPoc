from __future__ import annotations

from typing import Any

from doc2tests.contracts.enums import FieldType, RelationOp
from doc2tests.contracts.state import FieldSchema, GraphState
from doc2tests.contracts.template import CanonicalTemplate, Field, Relation

# label keywords that imply a start point vs an end point
_START_HINTS = ("חתימת", "חוזה", "התחלה", "start", "from")
_END_HINTS = ("כניסה", "סיום", "end", "to")


def _rank(field: Field) -> int:
    low = field.label.lower()
    if any(h.lower() in low for h in _START_HINTS):
        return 0
    if any(h.lower() in low for h in _END_HINTS):
        return 2
    return 1


def _date_order_relations(fields: list[Field]) -> list[Relation]:
    dates = [f for f in fields if f.type == FieldType.date]
    if len(dates) < 2:
        return []
    ordered = sorted(dates, key=_rank)
    relations: list[Relation] = []
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if earlier.id != later.id:
            relations.append(Relation(kind="order", op=RelationOp.le,
                                       left=earlier.id, right=later.id))
    return relations


def extract_schema(state: GraphState) -> dict[str, Any]:
    if state.template is None:
        return {"template": None, "field_schema": FieldSchema()}
    tmpl = state.template
    new_relations = list(tmpl.relations) + _date_order_relations(tmpl.fields)
    rebuilt = CanonicalTemplate(
        template_id=tmpl.template_id, doc_type=tmpl.doc_type, language=tmpl.language,
        direction=tmpl.direction, source=tmpl.source, layout_blocks=tmpl.layout_blocks,
        fields=tmpl.fields, relations=new_relations,
    )
    notes = {f.id: f.type.value for f in tmpl.fields}
    return {"template": rebuilt, "field_schema": FieldSchema(notes=notes)}

from __future__ import annotations

import random
from typing import Any

from doc2tests.contracts.enums import FieldType, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import GraphState
from doc2tests.contracts.template import CanonicalTemplate, Field
from doc2tests.generate.relations import violate_order
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import validate

# field types that carry a content validator we can deliberately break
_VALIDATED = {
    FieldType.israeli_id, FieldType.date, FieldType.gush_helka,
    FieldType.phone, FieldType.bank_branch,
}


def _class_counts(n: int, mix: dict[TestClass, float]) -> list[TestClass]:
    counts = {c: int(n * w) for c, w in mix.items()}
    while sum(counts.values()) < n:  # distribute rounding remainder
        counts[TestClass.equivalence] += 1
    seq: list[TestClass] = []
    for c, k in counts.items():
        seq.extend([c] * k)
    return seq[:n]


def _value_for(field: Field, cls: TestClass, rng: random.Random) -> str:
    strat = strategy_for(field.type, rng)
    if cls == TestClass.equivalence:
        return strat.equivalence()
    if cls == TestClass.boundary:
        return strat.boundary()
    neg = strat.negative()
    return rng.choice(neg) if neg else strat.equivalence()


def _validated_fields(template: CanonicalTemplate) -> list[Field]:
    return [f for f in template.fields if f.type in _VALIDATED]


def generate_population(state: GraphState) -> dict[str, Any]:
    if state.template is None:
        return {"population": []}
    tmpl = state.template
    rng = random.Random(state.config.seed)
    classes = _class_counts(state.config.n, state.config.mix)
    rng.shuffle(classes)
    records: list[Record] = []
    for i, cls in enumerate(classes):
        # generate a fully valid record first, then break one rule for negatives
        base_cls = TestClass.equivalence if cls == TestClass.negative else cls
        values: dict[str, str] = {f.id: _value_for(f, base_cls, rng) for f in tmpl.fields}

        violates: str | None = None
        if cls == TestClass.negative:
            violates = _inject_violation(tmpl, values, rng)

        record_values = {
            f.id: Value(field_id=f.id, value=values[f.id],
                        valid=validate(f.type, values[f.id]))
            for f in tmpl.fields
        }
        records.append(Record(
            index=i, test_class=cls,
            expected_valid=(cls != TestClass.negative),
            violates=violates, values=record_values,
        ))
    return {"population": records}


def _inject_violation(
    template: CanonicalTemplate, values: dict[str, str], rng: random.Random
) -> str:
    """Break exactly one rule: a validated field's value, or an order relation."""
    validated = _validated_fields(template)
    order_rels = [r for r in template.relations if r.kind == "order"]
    choices: list[str] = ["field"] * len(validated) + (["relation"] if order_rels else [])
    if not choices:
        return "none"
    pick = rng.choice(choices)
    if pick == "relation":
        values.update(violate_order(template, values))
        return "relation.order"
    field = rng.choice(validated)
    neg = strategy_for(field.type, rng).negative()
    if neg:
        values[field.id] = rng.choice(neg)
    return f"{field.type.value}.invalid"

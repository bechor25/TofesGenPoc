from __future__ import annotations

from doc2tests.contracts.enums import RelationOp
from doc2tests.contracts.template import CanonicalTemplate, Relation
from doc2tests.validators.dates import parse_il_date


def _order_relations(template: CanonicalTemplate) -> list[Relation]:
    return [r for r in template.relations
            if r.kind == "order" and r.left and r.right and r.op == RelationOp.le]


def satisfies_order(template: CanonicalTemplate, values: dict[str, str]) -> bool:
    for r in _order_relations(template):
        left = parse_il_date(values.get(r.left or "", ""))
        right = parse_il_date(values.get(r.right or "", ""))
        if left is not None and right is not None and left > right:
            return False
    return True


def violate_order(template: CanonicalTemplate, values: dict[str, str]) -> dict[str, str]:
    out = dict(values)
    for r in _order_relations(template):
        lid, rid = r.left or "", r.right or ""
        if lid in out and rid in out:
            out[lid], out[rid] = out[rid], out[lid]
            left = parse_il_date(out[lid])
            right = parse_il_date(out[rid])
            if left is not None and right is not None and left > right:
                return out
    return out

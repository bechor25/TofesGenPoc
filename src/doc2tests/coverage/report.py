from __future__ import annotations

from collections import Counter

from doc2tests.contracts.enums import FieldType, TestClass
from doc2tests.contracts.records import Record
from doc2tests.contracts.state import CoverageCell, CoverageReport
from doc2tests.contracts.template import CanonicalTemplate

_VALIDATED = {
    FieldType.israeli_id, FieldType.date, FieldType.gush_helka,
    FieldType.phone, FieldType.bank_branch,
}


def build_coverage(template: CanonicalTemplate, population: list[Record]) -> CoverageReport:
    per_class: Counter[TestClass] = Counter(r.test_class for r in population)
    cells: list[CoverageCell] = []
    for f in template.fields:
        for cls in TestClass:
            cells.append(CoverageCell(field_id=f.id, test_class=cls,
                                      count=per_class.get(cls, 0)))

    rules = sorted({r.violates for r in population if r.violates})
    tested_types = {r.violates.split(".")[0] for r in population if r.violates}
    gaps = [f"{f.id}:{f.type.value} has no negative coverage"
            for f in template.fields
            if f.type in _VALIDATED and f.type.value not in tested_types]
    return CoverageReport(cells=cells, rules_exercised=rules, gaps=gaps)

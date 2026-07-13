from __future__ import annotations

import random
from typing import Any

from doc2tests.common.logging import get_logger
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import DetectedValue, GraphState
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import validate

_log = get_logger("generate")


def _valid_value(field: DetectedValue, rng: random.Random, attempts: int = 8) -> str:
    """Generate a value that passes its validator (belt-and-suspenders retry)."""
    strat = strategy_for(field.field_type, rng)
    v = strat.generate()
    for _ in range(attempts):
        if validate(field.field_type, v):
            return v
        v = strat.generate()
    return v


def generate_population(state: GraphState) -> dict[str, Any]:
    personal = [d for d in state.detected if d.is_personal]
    if not personal:
        return {"population": []}
    rng = random.Random(state.config.seed)
    records: list[Record] = []
    for i in range(state.config.n):
        values = {
            d.id: Value(field_id=d.id, value=(nv := _valid_value(d, rng)),
                        valid=validate(d.field_type, nv))
            for d in personal
        }
        records.append(Record(index=i, values=values))
    _log.info("generated %d records for %d personal field(s)",
              len(records), len(personal))
    return {"population": records}

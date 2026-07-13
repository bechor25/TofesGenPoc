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
    """Generate a value that passes its validator (belt-and-suspenders retry).
    The original value is passed as ``like`` so shape-aware strategies (numbers,
    dates) can match its digit-count / separators."""
    strat = strategy_for(field.field_type, rng)
    v = strat.generate(field.value)
    for _ in range(attempts):
        if validate(field.field_type, v):
            return v
        v = strat.generate(field.value)
    return v


def _slot_key(d: DetectedValue) -> str:
    """The coherence key: fields the understanding agent tied to the same real-world
    entity share a slot and so one value. Slot-less fields key on their own id."""
    return f"slot:{d.slot}" if d.slot else f"id:{d.id}"


def generate_population(state: GraphState) -> dict[str, Any]:
    personal = [d for d in state.detected if d.is_personal]
    if not personal:
        return {"population": []}
    # one representative field per shared slot drives generation; members reuse its value
    leader: dict[str, DetectedValue] = {}
    for d in personal:
        leader.setdefault(_slot_key(d), d)
    rng = random.Random(state.config.seed)
    records: list[Record] = []
    for i in range(state.config.n):
        slot_value = {key: _valid_value(rep, rng) for key, rep in leader.items()}
        values = {
            d.id: Value(field_id=d.id, value=(nv := slot_value[_slot_key(d)]),
                        valid=validate(d.field_type, nv))
            for d in personal
        }
        records.append(Record(index=i, values=values))
    shared = len(personal) - len(leader)
    _log.info("generated %d records for %d personal field(s), %d shared into slots",
              len(records), len(personal), shared)
    # per-field trace on the first variant: original -> generated (+ valid?). Shows at a
    # glance whether each field got a sensible value for its type (e.g. address vs name).
    if records:
        for d in personal:
            v = records[0].values[d.id]
            _log.info("  generate | %-16s | %r: %r -> %r (valid=%s)",
                      d.field_type.value, d.label, d.value, v.value, v.valid)
    return {"population": records}

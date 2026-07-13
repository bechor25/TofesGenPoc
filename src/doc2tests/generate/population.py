from __future__ import annotations

import random
from typing import Any

from doc2tests.common.logging import get_logger
from doc2tests.contracts.enums import FieldType
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import DetectedValue, GraphState
from doc2tests.generate.data_agent import generate_text_variants
from doc2tests.generate.strategies import strategy_for
from doc2tests.providers.base import LLMProvider
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


def generate_population(
    state: GraphState, provider: LLMProvider | None = None
) -> dict[str, Any]:
    personal = [d for d in state.detected if d.is_personal]
    if not personal:
        return {"population": []}
    # one representative field per shared slot drives generation; members reuse its value
    leader: dict[str, DetectedValue] = {}
    for d in personal:
        leader.setdefault(_slot_key(d), d)
    # free-text (diagnosis / reason / description) has no local generator that reads as
    # real text — faker emits gibberish. The data agent writes believable, doc-aware
    # variants for those in one call; structured fields stay local + validated.
    doc_summary = state.parse_result.doc_summary if state.parse_result else ""
    free_leaders = [r for r in leader.values() if r.field_type == FieldType.free_text]
    llm: dict[str, list[str]] = {}
    if provider and free_leaders:
        llm = generate_text_variants(free_leaders, doc_summary, state.config.n, provider)
    rng = random.Random(state.config.seed)
    records: list[Record] = []
    for i in range(state.config.n):
        slot_value = {
            key: (llm[rep.id][i % len(llm[rep.id])] if rep.id in llm
                  else _valid_value(rep, rng))
            for key, rep in leader.items()
        }
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

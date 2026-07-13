import random

from doc2tests.contracts.enums import FieldType
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import validate


def test_every_typed_strategy_generates_a_valid_value():
    rng = random.Random(1)
    for ft in [FieldType.israeli_id, FieldType.date, FieldType.phone,
               FieldType.bank_branch, FieldType.gush_helka]:
        v = strategy_for(ft, rng).generate()
        assert validate(ft, v) is True, (ft, v)


def test_free_text_strategy_returns_nonempty():
    rng = random.Random(1)
    assert strategy_for(FieldType.free_text, rng).generate().strip()


def test_deterministic_with_same_seed():
    a = strategy_for(FieldType.israeli_id, random.Random(1)).generate()
    b = strategy_for(FieldType.israeli_id, random.Random(1)).generate()
    assert a == b

import random

from doc2tests.contracts.enums import FieldType
from doc2tests.generate.strategies import strategy_for
from doc2tests.validators import is_valid_il_date, is_valid_israeli_id


def _rng():
    return random.Random(42)


def test_israeli_id_equivalence_is_valid():
    s = strategy_for(FieldType.israeli_id, _rng())
    assert is_valid_israeli_id(s.equivalence())


def test_israeli_id_negative_is_invalid():
    s = strategy_for(FieldType.israeli_id, _rng())
    assert any(not is_valid_israeli_id(v) for v in s.negative())


def test_date_equivalence_is_valid():
    s = strategy_for(FieldType.date, _rng())
    assert is_valid_il_date(s.equivalence())


def test_date_negative_has_impossible_value():
    s = strategy_for(FieldType.date, _rng())
    assert any(not is_valid_il_date(v) for v in s.negative())


def test_hebrew_name_equivalence_nonempty():
    s = strategy_for(FieldType.hebrew_name, _rng())
    assert s.equivalence().strip()


def test_deterministic_with_same_seed():
    a = strategy_for(FieldType.israeli_id, random.Random(1)).equivalence()
    b = strategy_for(FieldType.israeli_id, random.Random(1)).equivalence()
    assert a == b


def test_unknown_type_falls_back_to_free_text():
    s = strategy_for(FieldType.free_text, _rng())
    assert isinstance(s.equivalence(), str)

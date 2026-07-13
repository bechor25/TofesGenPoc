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


def test_address_strategy_returns_single_line_nonempty():
    rng = random.Random(1)
    v = strategy_for(FieldType.address, rng).generate()
    assert v.strip() and "\n" not in v


def test_number_strategy_matches_original_digit_count():
    rng = random.Random(1)
    strat = strategy_for(FieldType.assessment_number, rng)
    for original in ["009007", "0012", "119128627"]:
        out = strat.generate(original)
        assert len(out) == len(original) and out.isdigit()


def test_date_strategy_era_matches_original_year():
    # regression: a generated date must stay near the ORIGINAL year, not jump to a
    # random very-old year. 2019 source -> 2018..2020; 1972 source -> 1971..1973.
    rng = random.Random(3)
    strat = strategy_for(FieldType.date, rng)
    for original, base in [("28/07/2019", 2019), ("28/04/1972", 1972)]:
        for _ in range(20):
            out = strat.generate(original)
            assert validate(FieldType.date, out) is True, out
            assert "/" in out                       # separator preserved
            year = int(out.rsplit("/", 1)[1])
            assert base - 1 <= year <= base + 1, (original, out)


def test_deterministic_with_same_seed():
    a = strategy_for(FieldType.israeli_id, random.Random(1)).generate()
    b = strategy_for(FieldType.israeli_id, random.Random(1)).generate()
    assert a == b

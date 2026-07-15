from doc2tests.imagegen.conditions import _num_conditions, photo_condition_clause


def test_level_1_and_below_is_empty():
    assert photo_condition_clause(1) == ""
    assert photo_condition_clause(0) == ""
    assert photo_condition_clause(-5) == ""


def test_level_states_the_number_and_asks_for_a_photo():
    clause = photo_condition_clause(5, seed=3)
    assert clause
    assert "Difficulty level 5 of 10" in clause
    assert "PHOTOGRAPH" in clause


def test_deterministic_per_level_and_seed():
    assert photo_condition_clause(6, seed=9) == photo_condition_clause(6, seed=9)


def test_condition_count_scales_with_level():
    assert _num_conditions(2) == 1
    assert _num_conditions(10) == 5
    assert _num_conditions(6) == 3
    # more conditions described at level 10 than level 2
    assert len(photo_condition_clause(10, seed=1)) > len(photo_condition_clause(2, seed=1))


def test_level_clamped_to_10():
    assert "Difficulty level 10 of 10" in photo_condition_clause(99)

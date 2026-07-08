from doc2tests.validators.gush_helka import is_valid_gush_helka, normalize_gush_helka


def test_valid_full():
    assert is_valid_gush_helka("9007-12-0") is True


def test_valid_without_sub():
    assert is_valid_gush_helka("9007-12") is True


def test_normalizes_leading_zeros_and_spaces():
    assert normalize_gush_helka("009007 / 0012 / 000") == "9007-12-0"


def test_rejects_missing_helka():
    assert is_valid_gush_helka("9007") is False


def test_rejects_non_numeric():
    assert is_valid_gush_helka("gush-12") is False

from datetime import date

from doc2tests.validators.dates import is_valid_il_date, parse_il_date


def test_parses_dotted_format():
    assert parse_il_date("31.10.21") == date(2021, 10, 31)


def test_parses_slashed_four_digit_year():
    assert parse_il_date("28/07/2019") == date(2019, 7, 28)


def test_parses_year_only():
    assert parse_il_date("2019") == date(2019, 1, 1)


def test_rejects_impossible_date():
    assert parse_il_date("31.02.21") is None
    assert is_valid_il_date("31.02.21") is False


def test_valid_true_for_real_date():
    assert is_valid_il_date("31.10.21") is True

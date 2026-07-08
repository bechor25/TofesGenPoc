from doc2tests.validators.contact import is_valid_bank_branch, is_valid_il_phone


def test_valid_mobile():
    assert is_valid_il_phone("0521234567") is True


def test_valid_landline_with_dash():
    assert is_valid_il_phone("04-6327888") is True


def test_rejects_wrong_length():
    assert is_valid_il_phone("12345") is False


def test_bank_branch_three_digits():
    assert is_valid_bank_branch("622") is True
    assert is_valid_bank_branch("420") is True


def test_bank_branch_rejects_non_numeric():
    assert is_valid_bank_branch("12X") is False

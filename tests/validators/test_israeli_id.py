from doc2tests.validators.israeli_id import complete_israeli_id, is_valid_israeli_id


def test_known_valid_id():
    assert is_valid_israeli_id("123456782") is True


def test_known_invalid_checksum():
    assert is_valid_israeli_id("123456789") is False


def test_pads_short_ids_with_leading_zeros():
    # 8-digit input is zero-padded to 9 before checking
    assert is_valid_israeli_id("00000001") == is_valid_israeli_id("000000001")


def test_rejects_non_digits():
    assert is_valid_israeli_id("12345678X") is False
    assert is_valid_israeli_id("") is False


def test_rejects_too_long():
    assert is_valid_israeli_id("1234567890") is False


def test_complete_produces_valid_id():
    full = complete_israeli_id("12345678")   # 8 digits -> add check digit
    assert len(full) == 9
    assert is_valid_israeli_id(full) is True

from doc2tests.contracts.enums import FieldType
from doc2tests.validators import validate


def test_registry_dispatches_israeli_id():
    assert validate(FieldType.israeli_id, "123456782") is True
    assert validate(FieldType.israeli_id, "123456789") is False


def test_registry_dispatches_date():
    assert validate(FieldType.date, "31.10.21") is True


def test_unknown_type_is_permissive():
    # free_text always valid
    assert validate(FieldType.free_text, "anything") is True

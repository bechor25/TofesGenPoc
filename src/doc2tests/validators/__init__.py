from __future__ import annotations

from collections.abc import Callable

from doc2tests.contracts.enums import FieldType
from doc2tests.validators.contact import is_valid_bank_branch, is_valid_il_phone
from doc2tests.validators.dates import is_valid_il_date
from doc2tests.validators.gush_helka import is_valid_gush_helka
from doc2tests.validators.israeli_id import is_valid_israeli_id

_REGISTRY: dict[FieldType, Callable[[str], bool]] = {
    FieldType.israeli_id: is_valid_israeli_id,
    FieldType.date: is_valid_il_date,
    FieldType.gush_helka: is_valid_gush_helka,
    FieldType.phone: is_valid_il_phone,
    FieldType.bank_branch: is_valid_bank_branch,
}


def validate(field_type: FieldType, value: str) -> bool:
    checker = _REGISTRY.get(field_type)
    return True if checker is None else checker(value)


__all__ = [
    "validate", "is_valid_israeli_id", "is_valid_il_date",
    "is_valid_gush_helka", "is_valid_il_phone", "is_valid_bank_branch",
]

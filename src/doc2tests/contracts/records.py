from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field as PField

from doc2tests.contracts.enums import TestClass


class Value(BaseModel):
    field_id: str
    value: str
    valid: bool = True


class Record(BaseModel):
    index: int
    test_class: TestClass
    expected_valid: bool
    violates: str | None = None          # rule key when expected_valid is False
    values: dict[str, Value] = PField(default_factory=dict)

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field as PField


class Value(BaseModel):
    field_id: str
    value: str
    valid: bool = True


class Record(BaseModel):
    index: int
    values: dict[str, Value] = PField(default_factory=dict)

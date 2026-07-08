from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, model_validator
from pydantic import Field as PField

from doc2tests.contracts.enums import (
    FieldType,
    PiiType,
    RelationOp,
    RenderStrategy,
    SourceKind,
    ValueKind,
)


class BBox(BaseModel):
    page: int = 1
    x: float
    y: float
    w: float
    h: float


class LayoutBlock(BaseModel):
    id: str
    kind: Literal["heading", "paragraph", "table", "field"]
    page: int = 1
    bbox: BBox | None = None


class Constraints(BaseModel):
    required: bool = False
    checksum: str | None = None          # validator key, e.g. "israeli_id"
    length: int | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    enum_values: list[str] | None = None


class Field(BaseModel):
    id: str
    label: str
    type: FieldType
    value_kind: ValueKind | None = None
    pii: bool = False
    pii_type: PiiType | None = None
    constraints: Constraints = PField(default_factory=Constraints)
    placeholder: str = ""
    bbox: BBox | None = None

    @model_validator(mode="after")
    def _default_placeholder(self) -> Field:
        if not self.placeholder:
            object.__setattr__(self, "placeholder", f"{{{{ {self.id} }}}}")
        return self


class Relation(BaseModel):
    kind: Literal["order", "derived"]
    op: RelationOp | None = None
    left: str | None = None
    right: str | None = None
    field: str | None = None
    from_fields: list[str] = PField(default_factory=list, alias="from")

    model_config = {"populate_by_name": True}


class DocSource(BaseModel):
    kind: SourceKind
    pages: int = 1
    render_strategy: RenderStrategy = RenderStrategy.reconstruct


class CanonicalTemplate(BaseModel):
    template_id: str = PField(default_factory=lambda: str(uuid.uuid4()))
    doc_type: str
    language: str = "he"
    direction: str = "rtl"
    source: DocSource
    layout_blocks: list[LayoutBlock] = PField(default_factory=list)
    fields: list[Field] = PField(default_factory=list)
    relations: list[Relation] = PField(default_factory=list)

    @model_validator(mode="after")
    def _check_integrity(self) -> CanonicalTemplate:
        ids = [f.id for f in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("field ids must be unique")
        idset = set(ids)
        for r in self.relations:
            for endpoint in (r.left, r.right, r.field, *r.from_fields):
                if endpoint is not None and endpoint not in idset:
                    raise ValueError(f"relation references unknown field: {endpoint}")
        return self

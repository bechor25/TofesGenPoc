from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field as PField

from doc2tests.contracts.records import Record
from doc2tests.contracts.state import DetectedValue


class DocumentResult(BaseModel):
    """The result of the CHEAP stages (ingest -> detect -> generate) for one file.
    ``page_image`` is kept so the expensive image-edit step can be run on demand,
    per variant, without re-processing the document."""
    path: str
    detected: list[DetectedValue] = PField(default_factory=list)
    population: list[Record] = PField(default_factory=list)
    page_image: bytes | None = None
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

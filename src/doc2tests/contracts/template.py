from __future__ import annotations

from pydantic import BaseModel


class BBox(BaseModel):
    page: int = 1
    x: float
    y: float
    w: float
    h: float

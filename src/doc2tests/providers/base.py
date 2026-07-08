from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel
from pydantic import Field as PField


class LLMResponse(BaseModel):
    text: str
    raw: dict[str, Any] = PField(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete_text(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> LLMResponse: ...

    def extract_vision(
        self, images: list[bytes], prompt: str, *, json_mode: bool = False
    ) -> LLMResponse: ...


class ProviderSpec(BaseModel):
    backend: Literal["openai", "ollama"]
    model: str


class NodeModelConfig(BaseModel):
    default: ProviderSpec
    overrides: dict[str, ProviderSpec] = PField(default_factory=dict)

    def for_node(self, node: str) -> ProviderSpec:
        return self.overrides.get(node, self.default)

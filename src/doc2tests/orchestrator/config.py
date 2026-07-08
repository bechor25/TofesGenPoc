from __future__ import annotations

import os

from doc2tests.providers.base import NodeModelConfig, ProviderSpec
from doc2tests.providers.openai_provider import OpenAIProvider


def default_node_config() -> NodeModelConfig:
    vision = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    return NodeModelConfig(default=ProviderSpec(backend="openai", model=vision))


def build_vision_provider() -> OpenAIProvider:
    """Construct the default OpenAI vision provider from the environment.

    Requires OPENAI_API_KEY to be present (loaded via .env by the app entrypoint).
    """
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    return OpenAIProvider(model=model)

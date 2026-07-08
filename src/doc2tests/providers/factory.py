from __future__ import annotations

from typing import Any

from doc2tests.providers.base import LLMProvider, NodeModelConfig, ProviderSpec
from doc2tests.providers.ollama_provider import OllamaProvider
from doc2tests.providers.openai_provider import OpenAIProvider


def build_provider(
    spec: ProviderSpec,
    *,
    openai_client: Any | None = None,
    ollama_session: Any | None = None,
    openai_api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
) -> LLMProvider:
    if spec.backend == "openai":
        return OpenAIProvider(model=spec.model, client=openai_client, api_key=openai_api_key)
    if spec.backend == "ollama":
        return OllamaProvider(model=spec.model, host=ollama_host, session=ollama_session)
    raise ValueError(f"unknown backend: {spec.backend}")


def provider_for_node(
    node: str,
    config: NodeModelConfig,
    *,
    openai_client: Any | None = None,
    ollama_session: Any | None = None,
    openai_api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
) -> LLMProvider:
    return build_provider(
        config.for_node(node),
        openai_client=openai_client,
        ollama_session=ollama_session,
        openai_api_key=openai_api_key,
        ollama_host=ollama_host,
    )

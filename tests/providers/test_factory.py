from doc2tests.providers.base import NodeModelConfig, ProviderSpec
from doc2tests.providers.factory import build_provider, provider_for_node
from doc2tests.providers.ollama_provider import OllamaProvider
from doc2tests.providers.openai_provider import OpenAIProvider


def test_build_openai_without_calling_network():
    p = build_provider(ProviderSpec(backend="openai", model="gpt-4o"),
                       openai_client=object())
    assert isinstance(p, OpenAIProvider)
    assert p.model == "gpt-4o"


def test_build_ollama():
    p = build_provider(ProviderSpec(backend="ollama", model="qwen2.5:7b"),
                       ollama_session=object())
    assert isinstance(p, OllamaProvider)


def test_provider_for_node_uses_override():
    cfg = NodeModelConfig(
        default=ProviderSpec(backend="openai", model="gpt-4o"),
        overrides={"generate_population": ProviderSpec(backend="ollama", model="qwen2.5:7b")},
    )
    p = provider_for_node("generate_population", cfg,
                          openai_client=object(), ollama_session=object())
    assert isinstance(p, OllamaProvider)

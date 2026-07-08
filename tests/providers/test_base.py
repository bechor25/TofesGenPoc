from doc2tests.providers.base import LLMResponse, NodeModelConfig, ProviderSpec


def test_llm_response_holds_text_and_raw():
    r = LLMResponse(text='{"a": 1}', raw={"model": "x"})
    assert r.text == '{"a": 1}'
    assert r.raw["model"] == "x"


def test_node_config_maps_nodes_to_specs():
    cfg = NodeModelConfig(
        default=ProviderSpec(backend="openai", model="gpt-4o"),
        overrides={"generate_population": ProviderSpec(backend="ollama", model="qwen2.5:7b")},
    )
    assert cfg.for_node("ingest_parse").backend == "openai"
    assert cfg.for_node("generate_population").backend == "ollama"

from __future__ import annotations

import os

from doc2tests.providers.base import LLMProvider
from doc2tests.providers.ollama_provider import OllamaProvider
from doc2tests.providers.openai_provider import OpenAIProvider


def build_image_provider() -> OpenAIProvider:
    """OpenAI provider for image editing (gpt-image-2). Requires OPENAI_API_KEY."""
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-5.1")
    image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    return OpenAIProvider(model=model, image_model=image_model)


def build_extract_provider() -> LLMProvider:
    """Provider for the two-stage grounded extraction (transcribe -> structure).

    Default: a strong CLOUD vision model (gpt-5.1) — much better on Hebrew than gpt-4o,
    fast (~30s/doc), and no local memory pressure. A local Qwen3-VL path exists
    (EXTRACT_BACKEND=ollama) but needs >32GB RAM to be practical; on a 32GB machine it
    swaps to disk and is unusably slow. OPENAI_VISION_MODEL overrides the cloud model.
    """
    backend = os.getenv("EXTRACT_BACKEND", "openai").lower()
    if backend == "ollama":
        model = os.getenv("OLLAMA_VL_MODEL", "qwen3-vl:8b")
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        return OllamaProvider(model=model, host=host, timeout=600)
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-5.1")
    image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    return OpenAIProvider(model=model, image_model=image_model)

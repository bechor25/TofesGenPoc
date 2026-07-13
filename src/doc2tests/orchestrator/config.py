from __future__ import annotations

import os

from doc2tests.providers.openai_provider import OpenAIProvider


def build_provider() -> OpenAIProvider:
    """OpenAI provider: extract_vision uses the vision model, edit_image uses
    gpt-image-2. One provider serves both. Requires OPENAI_API_KEY in the env."""
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    return OpenAIProvider(model=model)

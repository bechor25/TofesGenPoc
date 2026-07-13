from __future__ import annotations

import os

from doc2tests.providers.openai_provider import OpenAIProvider


def build_provider() -> OpenAIProvider:
    """OpenAI provider: extract_vision uses the vision model, edit_image uses the
    image model. One provider serves both. Requires OPENAI_API_KEY in the env.

    OPENAI_IMAGE_MODEL selects the image-edit model (default gpt-image-2). Use
    gpt-image-1 / gpt-image-1.5 to get input_fidelity=high (stronger source
    preservation for faithful document editing)."""
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    return OpenAIProvider(model=model, image_model=image_model)

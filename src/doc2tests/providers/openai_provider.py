from __future__ import annotations

import base64
import io
from typing import Any

from doc2tests.providers.base import LLMResponse


class OpenAIProvider:
    name = "openai"
    # models that accept input_fidelity=high (preserve the source, change only the
    # prompted values). gpt-image-2 rejects the param, so it is sent conditionally.
    _FIDELITY_MODELS = {"gpt-image-1", "gpt-image-1.5"}

    def __init__(
        self, model: str, client: Any | None = None, api_key: str | None = None,
        image_model: str = "gpt-image-2",
    ):
        self.model = model
        self.image_model = image_model
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)

    def _create(
        self, messages: list[dict[str, Any]], json_mode: bool, temperature: float = 0.0
    ) -> LLMResponse:
        # temperature=0 -> deterministic, stable extraction (no run-to-run drift)
        kwargs: dict[str, Any] = {
            "model": self.model, "messages": messages, "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        raw = resp.model_dump() if hasattr(resp, "model_dump") else {}
        return LLMResponse(text=text, raw=raw)

    def complete_text(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> LLMResponse:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._create(messages, json_mode)

    def extract_vision(
        self, images: list[bytes], prompt: str, *, json_mode: bool = False
    ) -> LLMResponse:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            b64 = base64.b64encode(img).decode("ascii")
            content.append({
                "type": "image_url",
                # detail:high -> full-resolution OCR, critical for Hebrew handwriting
                "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
            })
        return self._create([{"role": "user", "content": content}], json_mode)

    def edit_image(
        self, image: bytes, prompt: str, *,
        mask: bytes | None = None, size: str = "auto", quality: str = "high",
    ) -> bytes:
        # Reproduce the source, changing only the prompted values. images.edit needs
        # a named file-like for the image. input_fidelity=high preserves the original
        # but only some models accept it (gpt-image-2 rejects it) -> send conditionally.
        buf = io.BytesIO(image)
        buf.name = "form.png"
        kwargs: dict[str, Any] = {
            "model": self.image_model, "image": buf, "prompt": prompt,
            "size": size, "quality": quality,
        }
        if self.image_model in self._FIDELITY_MODELS:
            kwargs["input_fidelity"] = "high"
        if mask is not None:
            mbuf = io.BytesIO(mask)
            mbuf.name = "mask.png"
            kwargs["mask"] = mbuf
        resp = self._client.images.edit(**kwargs)
        return base64.b64decode(resp.data[0].b64_json)

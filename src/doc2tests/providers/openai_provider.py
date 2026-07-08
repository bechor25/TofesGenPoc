from __future__ import annotations

import base64
from typing import Any

from doc2tests.providers.base import LLMResponse


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, client: Any | None = None, api_key: str | None = None):
        self.model = model
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)

    def _create(self, messages: list[dict[str, Any]], json_mode: bool) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
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
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        return self._create([{"role": "user", "content": content}], json_mode)

from __future__ import annotations

import base64
from typing import Any

from doc2tests.providers.base import LLMResponse


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        session: Any | None = None,
        timeout: int = 120,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        if session is not None:
            self._session = session
        else:
            import requests

            self._session = requests.Session()

    def _generate(self, payload: dict[str, Any]) -> LLMResponse:
        payload = {"model": self.model, "stream": False, **payload}
        resp = self._session.post(
            f"{self.host}/api/generate", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(text=data.get("response", ""), raw=data)

    def complete_text(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> LLMResponse:
        payload: dict[str, Any] = {"prompt": prompt}
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        return self._generate(payload)

    def extract_vision(
        self, images: list[bytes], prompt: str, *, json_mode: bool = False
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "images": [base64.b64encode(img).decode("ascii") for img in images],
        }
        if json_mode:
            payload["format"] = "json"
        return self._generate(payload)

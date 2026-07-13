from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from doc2tests.api.app import create_app
from doc2tests.api.deps import get_extract_provider, get_image_provider
from doc2tests.providers.base import LLMResponse


class StubProvider:
    """Deterministic stand-in for the OpenAI provider (no network, no key).
    Vision returns one detectable field; edit echoes a marker so renders are
    checkable. Mirrors the stub in tests/orchestrator/test_graph.py."""

    name = "stub"

    def complete_text(self, *a: Any, **k: Any) -> LLMResponse:
        return LLMResponse(text="{}")

    def extract_vision(self, images: Any, prompt: str, *,
                       json_mode: bool = False) -> LLMResponse:
        return LLMResponse(text='{"raw_text":"t","fields":['
                                '{"label":"מספר זהות","value":"123456789"}]}')

    def edit_image(self, image: bytes, prompt: str, **k: Any) -> bytes:
        return b"PNGEDIT:" + image[:4]


@pytest.fixture
def stub() -> StubProvider:
    return StubProvider()


@pytest.fixture
def client(stub: StubProvider, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("doc2tests.ingest.parse.rasterize", lambda p: [b"IMGBYTES"])
    app = create_app()
    app.dependency_overrides[get_extract_provider] = lambda: stub
    app.dependency_overrides[get_image_provider] = lambda: stub
    return TestClient(app)


@pytest.fixture
def wait_job() -> Callable[[TestClient, str], dict[str, Any]]:
    def _wait(client: TestClient, job_id: str, tries: int = 400) -> dict[str, Any]:
        for _ in range(tries):
            j: dict[str, Any] = client.get(f"/api/jobs/{job_id}").json()
            if j["status"] != "running":
                return j
            time.sleep(0.02)
        raise AssertionError(f"job {job_id} did not finish")

    return _wait

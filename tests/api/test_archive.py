from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from doc2tests.api.app import create_app
from doc2tests.api.deps import get_extract_provider, get_image_provider
from doc2tests.db import repo

Wait = Callable[[TestClient, str], dict[str, Any]]


@pytest.fixture
def db_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
              stub: Any) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'archive.db'}")
    repo.reset()
    monkeypatch.setattr("doc2tests.ingest.parse.rasterize", lambda p: [b"IMGBYTES"])
    app = create_app()
    app.dependency_overrides[get_extract_provider] = lambda: stub
    app.dependency_overrides[get_image_provider] = lambda: stub
    yield TestClient(app)
    repo.reset()


def test_archive_flow_persists_source_and_generated(
    db_client: TestClient, wait_job: Wait
) -> None:
    ref = db_client.post("/api/extract",
                         files={"file": ("form.png", b"IMG", "image/png")}).json()
    wait_job(db_client, ref["job_id"])
    body = {"n": 1, "values": [
        {"label": "שם", "value": "דנה", "field_type": "hebrew_name",
         "is_personal": True}]}
    gr = db_client.post(f"/api/docs/{ref['doc_id']}/generate", json=body).json()
    wait_job(db_client, gr["job_id"])
    rr = db_client.post(f"/api/docs/{ref['doc_id']}/render",
                        json={"variant_index": 0}).json()
    wait_job(db_client, rr["job_id"])

    sources = db_client.get("/api/sources").json()
    assert len(sources) == 1
    assert sources[0]["n_generated"] == 1
    sid = sources[0]["id"]

    gens = db_client.get(f"/api/sources/{sid}/generated").json()
    assert len(gens) == 1
    gid = gens[0]["id"]

    img = db_client.get(f"/api/image/archived/{gid}")
    assert img.status_code == 200
    assert img.content.startswith(b"PNGEDIT:")

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

Wait = Callable[[TestClient, str], dict[str, Any]]


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

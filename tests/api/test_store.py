from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

Wait = Callable[[TestClient, str], dict[str, Any]]


def _upload_one(client: TestClient) -> int:
    r = client.post("/api/sources/upload",
                    files=[("files", ("form.png", b"IMG", "image/png"))])
    assert r.status_code == 200
    ids = r.json()["source_ids"]
    assert len(ids) == 1
    return ids[0]


def test_upload_creates_source_in_store(db_client: TestClient) -> None:
    sid = _upload_one(db_client)
    sources = db_client.get("/api/sources").json()
    assert len(sources) == 1
    s = sources[0]
    assert s["id"] == sid
    assert s["has_page_image"] is True
    assert s["has_detected"] is False       # lazy: no extraction on upload
    assert s["n_generated"] == 0
    assert db_client.get(f"/api/image/source/{sid}").status_code == 200


def test_upload_requires_db(client: TestClient) -> None:
    r = client.post("/api/sources/upload",
                    files=[("files", ("f.png", b"IMG", "image/png"))])
    assert r.status_code == 503


def test_open_extracts_then_caches(db_client: TestClient, wait_job: Wait) -> None:
    sid = _upload_one(db_client)

    op = db_client.post(f"/api/sources/{sid}/open").json()
    assert op["cached"] is False
    assert op["job_id"]
    wait_job(db_client, op["job_id"])

    doc = db_client.get(f"/api/docs/{op['doc_id']}").json()
    assert doc["detected"]
    assert doc["detected"][0]["field_type"] == "israeli_id"

    # extraction is now cached under the source
    assert db_client.get("/api/sources").json()[0]["has_detected"] is True

    op2 = db_client.post(f"/api/sources/{sid}/open").json()
    assert op2["cached"] is True
    assert op2["job_id"] is None
    doc2 = db_client.get(f"/api/docs/{op2['doc_id']}").json()
    assert doc2["detected"][0]["field_type"] == "israeli_id"


def test_open_force_reextracts(db_client: TestClient, wait_job: Wait) -> None:
    sid = _upload_one(db_client)
    op = db_client.post(f"/api/sources/{sid}/open").json()
    wait_job(db_client, op["job_id"])
    op2 = db_client.post(f"/api/sources/{sid}/open?force=true").json()
    assert op2["cached"] is False
    assert op2["job_id"]
    wait_job(db_client, op2["job_id"])


def test_open_missing_source_404(db_client: TestClient) -> None:
    assert db_client.post("/api/sources/999/open").status_code == 404


def test_full_run_from_store_and_edits_persist(
    db_client: TestClient, wait_job: Wait
) -> None:
    sid = _upload_one(db_client)
    op = db_client.post(f"/api/sources/{sid}/open").json()
    wait_job(db_client, op["job_id"])
    doc_id = op["doc_id"]

    body = {"n": 1, "values": [
        {"label": "שם מלא", "value": "דנה כהן", "field_type": "hebrew_name",
         "is_personal": True, "slot": None}]}
    gr = db_client.post(f"/api/docs/{doc_id}/generate", json=body).json()
    wait_job(db_client, gr["job_id"])
    rr = db_client.post(f"/api/docs/{doc_id}/render", json={"variant_index": 0}).json()
    wait_job(db_client, rr["job_id"])

    # generated image saved under the parent source
    s = db_client.get("/api/sources").json()[0]
    assert s["n_generated"] == 1

    # re-open reuses the REVIEWED (edited) values, not the raw extraction
    op2 = db_client.post(f"/api/sources/{sid}/open").json()
    assert op2["cached"] is True
    doc2 = db_client.get(f"/api/docs/{op2['doc_id']}").json()
    assert "שם מלא" in [d["label"] for d in doc2["detected"]]

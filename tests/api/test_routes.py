from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

Wait = Callable[[TestClient, str], dict[str, Any]]


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_extract_then_doc(client: TestClient, wait_job: Wait) -> None:
    r = client.post("/api/extract", files={"file": ("form.png", b"IMG", "image/png")})
    assert r.status_code == 200
    ref = r.json()
    job = wait_job(client, ref["job_id"])
    assert job["status"] == "done"

    doc = client.get(f"/api/docs/{ref['doc_id']}").json()
    assert doc["detected"]
    assert doc["detected"][0]["field_type"] == "israeli_id"
    assert doc["page_image_url"]
    assert client.get(doc["page_image_url"]).status_code == 200


def test_unknown_doc_and_job_404(client: TestClient) -> None:
    assert client.get("/api/docs/nope").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404


def test_bad_filetype_rejected(client: TestClient) -> None:
    r = client.post("/api/extract", files={"file": ("x.exe", b"IMG", "application/x")})
    assert r.status_code == 400


def test_generate_slot_coherence(client: TestClient, wait_job: Wait) -> None:
    ref = client.post("/api/extract",
                      files={"file": ("f.png", b"IMG", "image/png")}).json()
    wait_job(client, ref["job_id"])
    body = {"n": 3, "values": [
        {"label": "נמען", "value": "דנה כהן", "field_type": "hebrew_name",
         "is_personal": True, "slot": "recipient"},
        {"label": "חתימה", "value": "דנה כהן", "field_type": "hebrew_name",
         "is_personal": True, "slot": "recipient"},
    ]}
    gr = client.post(f"/api/docs/{ref['doc_id']}/generate", json=body).json()
    wait_job(client, gr["job_id"])

    doc = client.get(f"/api/docs/{ref['doc_id']}").json()
    assert len(doc["variants"]) == 3
    cols = [c["id"] for c in doc["columns"]]
    assert len(cols) == 2
    for v in doc["variants"]:  # same slot -> identical value every variant
        assert v["values"][cols[0]] == v["values"][cols[1]]


def test_render_and_zip(client: TestClient, wait_job: Wait) -> None:
    ref = client.post("/api/extract",
                      files={"file": ("f.png", b"IMG", "image/png")}).json()
    wait_job(client, ref["job_id"])
    body = {"n": 2, "values": [
        {"label": "שם", "value": "דנה", "field_type": "hebrew_name",
         "is_personal": True}]}
    gr = client.post(f"/api/docs/{ref['doc_id']}/generate", json=body).json()
    wait_job(client, gr["job_id"])

    rr = client.post(f"/api/docs/{ref['doc_id']}/render",
                     json={"variant_index": 0}).json()
    wait_job(client, rr["job_id"])

    img = client.get(f"/api/image/generated/{ref['doc_id']}/0")
    assert img.status_code == 200
    assert img.content.startswith(b"PNGEDIT:")

    doc = client.get(f"/api/docs/{ref['doc_id']}").json()
    assert doc["variants"][0]["rendered"] is True

    z = client.get(f"/api/docs/{ref['doc_id']}/zip")
    assert z.status_code == 200
    assert z.headers["content-type"] == "application/zip"


def test_render_bad_index(client: TestClient, wait_job: Wait) -> None:
    ref = client.post("/api/extract",
                      files={"file": ("f.png", b"IMG", "image/png")}).json()
    wait_job(client, ref["job_id"])
    body = {"n": 1, "values": [
        {"label": "שם", "value": "דנה", "field_type": "hebrew_name",
         "is_personal": True}]}
    gr = client.post(f"/api/docs/{ref['doc_id']}/generate", json=body).json()
    wait_job(client, gr["job_id"])
    r = client.post(f"/api/docs/{ref['doc_id']}/render", json={"variant_index": 9})
    assert r.status_code == 400


def test_batch(client: TestClient, wait_job: Wait) -> None:
    files = [("files", ("a.png", b"IMG", "image/png")),
             ("files", ("b.png", b"IMG", "image/png"))]
    r = client.post("/api/batch", files=files, data={"n": "2", "workers": "1"})
    ref = r.json()
    job = wait_job(client, ref["job_id"])
    assert job["status"] == "done"
    res = job["result"]
    assert len(res) == 2
    for item in res:
        assert item["doc_id"].startswith("doc-")
        d = client.get(f"/api/docs/{item['doc_id']}").json()
        assert d["doc_id"] == item["doc_id"]


def test_logs(client: TestClient) -> None:
    client.post("/api/extract", files={"file": ("f.png", b"IMG", "image/png")})
    lines = client.get("/api/logs?n=50").json()["lines"]
    assert isinstance(lines, list)

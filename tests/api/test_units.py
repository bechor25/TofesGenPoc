from __future__ import annotations

import time

import pytest

from doc2tests.api.jobs import JobManager
from doc2tests.api.schemas import (
    DetectedDTO,
    ReviewedValueDTO,
    reviewed_to_detected,
)
from doc2tests.api.status import friendly_stage
from doc2tests.api.workspace import WorkspaceStore
from doc2tests.contracts.enums import FieldType
from doc2tests.contracts.state import DetectedValue


def _drain(jm: JobManager, job_id: str) -> None:
    for _ in range(400):
        if jm.get(job_id).status != "running":
            return
        time.sleep(0.01)
    raise AssertionError("job did not finish")


# --- schemas ---
def test_from_detected() -> None:
    d = DetectedValue(id="x", label="שם", value="דנה",
                      field_type=FieldType.hebrew_name, is_personal=True, slot="s1")
    dto = DetectedDTO.from_detected(d)
    assert dto.field_type == "hebrew_name"
    assert dto.slot == "s1"
    assert dto.is_personal is True


def test_reviewed_to_detected_maps_and_drops_blanks() -> None:
    out = reviewed_to_detected([
        ReviewedValueDTO(label="שם", value="דנה", field_type="hebrew_name",
                         is_personal=True, slot="s"),
        ReviewedValueDTO(label="", value="", is_personal=False),  # dropped
        ReviewedValueDTO(label="הערה", value="x", field_type="bogus"),  # -> free_text
    ])
    assert len(out) == 2
    assert out[0].field_type == FieldType.hebrew_name
    assert out[0].slot == "s"
    assert out[1].field_type == FieldType.free_text
    assert len({d.id for d in out}) == 2  # unique ids


# --- status ---
def test_friendly_stage() -> None:
    assert friendly_stage(
        ["12:00 INFO doc2tests.ingest | grounded transcribe: reading 1 page"]
    ) == "מתעתק כל טקסט מהמסמך"
    assert friendly_stage([]) == ""


# --- workspace ---
def test_workspace_new_get_and_missing() -> None:
    s = WorkspaceStore()
    doc_id = s.new("a.png")
    assert doc_id == "doc-1"
    assert s.get(doc_id).filename == "a.png"
    with pytest.raises(KeyError):
        s.get("nope")


def test_as_document_result() -> None:
    s = WorkspaceStore()
    doc_id = s.new("f.png")
    ws = s.get(doc_id)
    ws.page_image = b"IMG"
    ws.detected = [DetectedValue(id="x", label="l", value="v", is_personal=True)]
    dr = s.as_document_result(doc_id)
    assert dr.page_image == b"IMG"
    assert dr.path == "f.png"
    assert dr.detected[0].id == "x"


# --- jobs ---
def test_job_runs_and_events() -> None:
    jm = JobManager()
    job_id = jm.start(lambda: 42)
    _drain(jm, job_id)
    job = jm.get(job_id)
    assert job.status == "done"
    assert job.result == 42
    frames = list(jm.events(job_id))
    assert frames
    assert '"done": true' in frames[-1]


def test_job_captures_error() -> None:
    jm = JobManager()

    def boom() -> int:
        raise ValueError("nope")

    job_id = jm.start(boom)
    _drain(jm, job_id)
    job = jm.get(job_id)
    assert job.status == "error"
    assert "nope" in (job.error or "")

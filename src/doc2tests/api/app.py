"""FastAPI application: routes + static SPA mount.

Every route is a thin wrapper around the UNCHANGED pipeline stage functions.
Slow steps (extract / generate / render / batch) start a background job and
return a ``job_id``; the SPA streams live status from ``GET /api/jobs/{id}/events``
and refetches ``GET /api/docs/{doc_id}`` when the job finishes.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from doc2tests.api.deps import (
    get_extract_provider,
    get_image_provider,
    get_jobs,
    get_store,
)
from doc2tests.api.jobs import JobManager
from doc2tests.api.schemas import (
    BatchItemDTO,
    ColumnDTO,
    DetectedDTO,
    DiagnosticsRowDTO,
    DocStateDTO,
    GeneratedDTO,
    GenerateReq,
    JobRef,
    JobStatusDTO,
    OpenResult,
    RenderReq,
    ReviewedValueDTO,
    SourceDTO,
    UploadResult,
    VariantDTO,
    reviewed_to_detected,
)
from doc2tests.api.workspace import Workspace, WorkspaceStore
from doc2tests.common.logging import get_logger, recent_logs
from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import (
    DetectedValue,
    GraphState,
    InputRef,
    ParseResult,
    RunConfig,
)
from doc2tests.db import repo
from doc2tests.deid.detect import detect_fields
from doc2tests.generate.population import generate_population
from doc2tests.ingest.grounded import extract_grounded
from doc2tests.ingest.loaders import detect_kind
from doc2tests.ingest.parse import ingest_parse
from doc2tests.ingest.rasterize import rasterize
from doc2tests.orchestrator.batch import process_batch, render_variant
from doc2tests.providers.base import LLMProvider
from doc2tests.ui.helpers import zip_images

_log = get_logger("api")


# --- helpers ------------------------------------------------------------------------
def _save_temp(filename: str, data: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=Path(filename).suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _get_ws(store: WorkspaceStore, doc_id: str) -> Workspace:
    try:
        return store.get(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="doc not found") from None


def _variant_labels(ws: Workspace, index: int) -> dict[str, str]:
    """{label: generated value} for the personal fields of one variant (as stored)."""
    rec = ws.population[index]
    return {d.label: rec.values[d.id].value for d in ws.detected if d.id in rec.values}


def _doc_state(ws: Workspace) -> DocStateDTO:
    detected = [DetectedDTO.from_detected(d) for d in ws.detected]
    columns = [ColumnDTO(id=d.id, label=d.label) for d in ws.detected if d.is_personal]
    variants = [
        VariantDTO(index=r.index,
                   values={fid: v.value for fid, v in r.values.items()},
                   rendered=r.index in ws.rendered)
        for r in ws.population
    ]
    first = ws.population[0].values if ws.population else {}
    diagnostics = [
        DiagnosticsRowDTO(
            label=d.label, field_type=d.field_type.value, is_personal=d.is_personal,
            slot=d.slot, original=d.value,
            generated=(first[d.id].value if d.id in first else "—"))
        for d in ws.detected
    ]
    page_url = f"/api/image/page/{ws.doc_id}" if ws.page_image else None
    return DocStateDTO(
        doc_id=ws.doc_id, filename=ws.filename, doc_summary=ws.doc_summary,
        page_image_url=page_url, detected=detected, columns=columns,
        variants=variants, diagnostics=diagnostics)


# --- background job bodies (run on a worker thread) ---------------------------------
def _run_extract(store: WorkspaceStore, doc_id: str, path: str,
                 kind: SourceKind, provider: LLMProvider) -> dict[str, Any]:
    ws = store.get(doc_id)
    st = GraphState(input_ref=InputRef(path=path, kind=kind))
    st = st.model_copy(update=ingest_parse(st, provider))
    st = st.model_copy(update=detect_fields(st))
    ws.page_image = st.page_images[0] if st.page_images else None
    ws.detected = st.detected
    ws.doc_summary = st.parse_result.doc_summary if st.parse_result else ""
    if st.errors:
        raise RuntimeError(st.errors[0].message)
    return {"doc_id": doc_id, "n_detected": len(ws.detected)}


def _run_open_extract(store: WorkspaceStore, doc_id: str, source_id: int,
                      provider: LLMProvider) -> dict[str, Any]:
    """Extract a STORED source (page image already in the workspace), then cache the
    result under the source so future runs skip the paid gpt-5.1 call."""
    ws = store.get(doc_id)
    images = [ws.page_image] if ws.page_image is not None else []
    raw_text, summary, fields = extract_grounded(images, provider)
    pr = ParseResult(raw_text=raw_text, doc_summary=summary, fields=fields,
                     provider=provider.name)
    st = GraphState(input_ref=InputRef(path=ws.filename, kind=SourceKind.image),
                    parse_result=pr)
    st = st.model_copy(update=detect_fields(st))
    ws.detected = st.detected
    ws.doc_summary = summary
    repo.set_extraction(source_id, summary,
                        [d.model_dump(mode="json") for d in ws.detected])
    return {"n_detected": len(ws.detected)}


def _run_generate(store: WorkspaceStore, doc_id: str,
                  values: list[ReviewedValueDTO], n: int,
                  provider: LLMProvider) -> dict[str, Any]:
    ws = store.get(doc_id)
    ws.detected = reviewed_to_detected(values)
    ws.rendered = {}  # values changed -> old renders no longer match
    st = GraphState(
        input_ref=InputRef(path=ws.filename, kind=SourceKind.image),
        detected=ws.detected, config=RunConfig(n=n),
        parse_result=ParseResult(doc_summary=ws.doc_summary))
    st = st.model_copy(update=generate_population(st, provider))
    ws.population = st.population
    if ws.source_id is None:
        ws.source_id = repo.save_source(ws.filename, ws.page_image, ws.doc_summary)
    # cache the REVIEWED values under the source, so the next run reuses the user's edits
    if ws.source_id is not None:
        repo.set_extraction(ws.source_id, ws.doc_summary,
                            [d.model_dump(mode="json") for d in ws.detected])
    return {"n_variants": len(ws.population)}


def _run_render(store: WorkspaceStore, doc_id: str, index: int,
                provider: LLMProvider) -> dict[str, Any]:
    ws = store.get(doc_id)
    doc = store.as_document_result(doc_id)
    img = render_variant(doc, index, provider)
    ws.rendered[index] = img
    if ws.source_id is None:
        ws.source_id = repo.save_source(ws.filename, ws.page_image, ws.doc_summary)
    if ws.source_id is not None:
        repo.save_generated(ws.source_id, index, _variant_labels(ws, index), img)
    return {"index": index}


def _run_batch(store: WorkspaceStore, saved: list[tuple[str, str]], n: int,
               workers: int, provider: LLMProvider) -> list[dict[str, Any]]:
    names = [nm for nm, _ in saved]
    paths = [p for _, p in saved]
    results = process_batch(paths, provider, n=n, max_workers=workers)
    out: list[dict[str, Any]] = []
    for name, doc in zip(names, results, strict=False):
        doc_id = store.new(name)
        ws = store.get(doc_id)
        ws.page_image = doc.page_image
        ws.detected = doc.detected
        ws.population = doc.population
        ws.doc_summary = doc.doc_summary
        ws.source_id = repo.save_source(name, doc.page_image, doc.doc_summary)
        out.append(BatchItemDTO(doc_id=doc_id, filename=name,
                                n_variants=len(doc.population),
                                error=doc.error).model_dump())
    return out


def _frontend_dist() -> Path:
    override = os.getenv("FRONTEND_DIST")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


# --- app ----------------------------------------------------------------------------
def create_app() -> FastAPI:
    load_dotenv()  # local dev picks up .env; in Docker the env is already set
    app = FastAPI(title="מחולל טפסים API")
    app.state.store = WorkspaceStore()
    app.state.jobs = JobManager()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/extract", response_model=JobRef)
    async def extract(
        file: UploadFile = File(...),
        store: WorkspaceStore = Depends(get_store),
        jobs: JobManager = Depends(get_jobs),
        provider: LLMProvider = Depends(get_extract_provider),
    ) -> JobRef:
        filename = file.filename or "upload"
        try:
            kind = SourceKind(detect_kind(filename))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        path = _save_temp(filename, await file.read())
        doc_id = store.new(filename)
        job_id = jobs.start(lambda: _run_extract(store, doc_id, path, kind, provider))
        return JobRef(job_id=job_id, doc_id=doc_id)

    @app.get("/api/jobs/{job_id}/events")
    def job_events(job_id: str, jobs: JobManager = Depends(get_jobs)) -> StreamingResponse:
        try:
            jobs.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        return StreamingResponse(
            jobs.events(job_id), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/jobs/{job_id}", response_model=JobStatusDTO)
    def job_status(job_id: str, jobs: JobManager = Depends(get_jobs)) -> JobStatusDTO:
        try:
            job = jobs.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        return JobStatusDTO(id=job.id, status=job.status, error=job.error,
                            result=job.result)

    @app.get("/api/docs/{doc_id}", response_model=DocStateDTO)
    def get_doc(doc_id: str, store: WorkspaceStore = Depends(get_store)) -> DocStateDTO:
        return _doc_state(_get_ws(store, doc_id))

    @app.get("/api/image/page/{doc_id}")
    def page_image(doc_id: str, store: WorkspaceStore = Depends(get_store)) -> Response:
        ws = _get_ws(store, doc_id)
        if ws.page_image is None:
            raise HTTPException(status_code=404, detail="no page image")
        return Response(content=ws.page_image, media_type="image/png")

    @app.post("/api/docs/{doc_id}/generate", response_model=JobRef)
    def generate(
        doc_id: str, req: GenerateReq,
        store: WorkspaceStore = Depends(get_store),
        jobs: JobManager = Depends(get_jobs),
        provider: LLMProvider = Depends(get_extract_provider),
    ) -> JobRef:
        _get_ws(store, doc_id)
        job_id = jobs.start(
            lambda: _run_generate(store, doc_id, req.values, req.n, provider))
        return JobRef(job_id=job_id, doc_id=doc_id)

    @app.post("/api/docs/{doc_id}/render", response_model=JobRef)
    def render(
        doc_id: str, req: RenderReq,
        store: WorkspaceStore = Depends(get_store),
        jobs: JobManager = Depends(get_jobs),
        provider: LLMProvider = Depends(get_image_provider),
    ) -> JobRef:
        ws = _get_ws(store, doc_id)
        if not ws.population:
            raise HTTPException(status_code=400, detail="no data generated yet")
        if not 0 <= req.variant_index < len(ws.population):
            raise HTTPException(status_code=400, detail="variant index out of range")
        job_id = jobs.start(
            lambda: _run_render(store, doc_id, req.variant_index, provider))
        return JobRef(job_id=job_id, doc_id=doc_id)

    @app.get("/api/image/generated/{doc_id}/{index}")
    def generated_image(
        doc_id: str, index: int, store: WorkspaceStore = Depends(get_store),
    ) -> Response:
        ws = _get_ws(store, doc_id)
        if index not in ws.rendered:
            raise HTTPException(status_code=404, detail="not rendered")
        return Response(content=ws.rendered[index], media_type="image/png")

    @app.get("/api/docs/{doc_id}/zip")
    def doc_zip(doc_id: str, store: WorkspaceStore = Depends(get_store)) -> Response:
        ws = _get_ws(store, doc_id)
        if not ws.rendered:
            raise HTTPException(status_code=404, detail="nothing rendered")
        prefix = Path(ws.filename).stem or "form"
        data = zip_images([ws.rendered[i] for i in sorted(ws.rendered)], prefix=prefix)
        return Response(
            content=data, media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{prefix}_forms.zip"'})

    @app.post("/api/batch", response_model=JobRef)
    async def batch(
        files: list[UploadFile] = File(...),
        n: int = Form(10),
        workers: int = Form(4),
        store: WorkspaceStore = Depends(get_store),
        jobs: JobManager = Depends(get_jobs),
        provider: LLMProvider = Depends(get_extract_provider),
    ) -> JobRef:
        saved: list[tuple[str, str]] = []
        for f in files:
            name = f.filename or "upload"
            saved.append((name, _save_temp(name, await f.read())))
        job_id = jobs.start(lambda: _run_batch(store, saved, n, workers, provider))
        return JobRef(job_id=job_id)

    @app.post("/api/sources/upload", response_model=UploadResult)
    async def upload_sources(
        files: list[UploadFile] = File(...),
        store: WorkspaceStore = Depends(get_store),
    ) -> UploadResult:
        """Add document(s) to the store: rasterize + persist each as a source NOW (no
        extraction — that happens lazily on the first run). Returns the source ids."""
        if not repo.available():
            raise HTTPException(status_code=503,
                                detail="persistence off — set DATABASE_URL")
        ids: list[int] = []
        for f in files:
            name = f.filename or "upload"
            path = _save_temp(name, await f.read())
            try:
                images = rasterize(path)
            except Exception as exc:  # noqa: BLE001 - bad file -> 400, not a 500
                raise HTTPException(status_code=400, detail=f"{name}: {exc}") from None
            page = images[0] if images else None
            sid = repo.save_source(name, page, "")
            if sid is not None:
                ids.append(sid)
        return UploadResult(source_ids=ids)

    @app.get("/api/image/source/{source_id}")
    def source_image(source_id: int) -> Response:
        full = repo.get_source(source_id)
        if full is None or full.page_image is None:
            raise HTTPException(status_code=404, detail="not found")
        return Response(content=full.page_image, media_type="image/png")

    @app.post("/api/sources/{source_id}/open", response_model=OpenResult)
    def open_source(
        source_id: int, force: bool = False,
        store: WorkspaceStore = Depends(get_store),
        jobs: JobManager = Depends(get_jobs),
        provider: LLMProvider = Depends(get_extract_provider),
    ) -> OpenResult:
        """Open a stored source to run the flow. Builds a workspace from its page image.
        If a cached extraction exists (and not force), it's reused -> ready for review
        immediately, no gpt-5.1 call. Otherwise an extraction job starts."""
        full = repo.get_source(source_id)
        if full is None:
            raise HTTPException(status_code=404, detail="source not found")
        doc_id = store.new(full.filename)
        ws = store.get(doc_id)
        ws.page_image = full.page_image
        ws.doc_summary = full.doc_summary
        ws.source_id = source_id
        if full.detected and not force:
            ws.detected = [DetectedValue(**d) for d in full.detected]
            return OpenResult(doc_id=doc_id, job_id=None, cached=True)
        job_id = jobs.start(
            lambda: _run_open_extract(store, doc_id, source_id, provider))
        return OpenResult(doc_id=doc_id, job_id=job_id, cached=False)

    @app.get("/api/sources", response_model=list[SourceDTO])
    def sources() -> list[SourceDTO]:
        return [SourceDTO(id=s.id, filename=s.filename, doc_summary=s.doc_summary,
                          n_generated=s.n_generated, has_page_image=s.has_page_image,
                          has_detected=s.has_detected) for s in repo.list_sources()]

    @app.get("/api/sources/{source_id}/generated", response_model=list[GeneratedDTO])
    def source_generated(source_id: int) -> list[GeneratedDTO]:
        return [GeneratedDTO(id=g.id, variant_index=g.variant_index, values=g.values)
                for g in repo.list_generated(source_id)]

    @app.get("/api/image/archived/{generated_id}")
    def archived_image(generated_id: int) -> Response:
        img = repo.get_image(generated_id)
        if img is None:
            raise HTTPException(status_code=404, detail="not found")
        return Response(content=img, media_type="image/png")

    @app.get("/api/logs")
    def logs(n: int = 400) -> dict[str, list[str]]:
        return {"lines": recent_logs(n)}

    dist = _frontend_dist()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")
    else:
        _log.info("frontend dist not found at %s — API only (build the SPA)", dist)

    return app

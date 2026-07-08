"""Minimal FastAPI wrapper around the LangGraph workflow.

Two-step human-in-the-loop:
  POST /runs                 -> extract template, pause at review gate
  POST /runs/{tid}/approve   -> apply edits, generate + render, return results

Run with:  uv run uvicorn doc2tests.api.main:app --reload
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.ingest.loaders import detect_kind
from doc2tests.orchestrator.config import build_vision_provider
from doc2tests.orchestrator.graph import build_graph

load_dotenv()

app = FastAPI(title="doc2tests")
OUTPUT_ROOT = Path("output")
_RUNS: dict[str, Any] = {}


class ApproveRequest(BaseModel):
    edits: dict[str, str] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs")
async def create_run(
    file: UploadFile = File(...),
    n: int = Form(20),
    formats: str = Form("html,docx"),
    seed: int = Form(42),
) -> dict[str, Any]:
    thread_id = f"api-{abs(hash(file.filename)) % 100000}"
    out_dir = OUTPUT_ROOT / thread_id
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "input.jpg").suffix.lower() or ".jpg"
    input_path = out_dir / f"input{suffix}"
    input_path.write_bytes(await file.read())

    graph = build_graph(build_vision_provider(), str(out_dir))
    config = {"configurable": {"thread_id": thread_id}}
    state = GraphState(
        input_ref=InputRef(path=str(input_path), kind=SourceKind(detect_kind(str(input_path)))),
        config=RunConfig(n=n, seed=seed, formats=formats.split(",")),
    )
    graph.invoke(state, config)
    snap = graph.get_state(config)
    _RUNS[thread_id] = graph
    template = snap.values["template"]
    return {
        "thread_id": thread_id,
        "doc_type": template.doc_type,
        "fields": [{"id": f.id, "label": f.label, "type": f.type.value, "pii": f.pii}
                   for f in template.fields],
        "relations": [{"left": r.left, "op": r.op.value if r.op else None, "right": r.right}
                      for r in template.relations if r.kind == "order"],
        "errors": [e.message for e in snap.values.get("errors", [])],
    }


@app.post("/runs/{thread_id}/approve")
def approve_run(thread_id: str, req: ApproveRequest) -> dict[str, Any]:
    graph = _RUNS.get(thread_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="unknown run")
    config = {"configurable": {"thread_id": thread_id}}
    graph.update_state(config, {"review": {"approved": True, "edits": req.edits}})
    final = graph.invoke(None, config)
    coverage = final["coverage"]
    return {
        "population_size": len(final["population"]),
        "rules_exercised": coverage.rules_exercised if coverage else [],
        "gaps": coverage.gaps if coverage else [],
        "outputs": [{"record": d.record_index, "fmt": d.fmt, "path": d.path}
                    for d in final["outputs"]],
    }

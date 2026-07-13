"""Batch processing for scale: run the CHEAP stages (ingest -> detect -> generate)
over many files, then render images ON DEMAND per variant.

The data stage (vision extraction + local, validated generation) is cheap and
scales freely — run it across a whole folder. The image-edit stage is expensive,
so it is a separate explicit call (``render_variant``) the caller meters.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from doc2tests.common.logging import get_logger
from doc2tests.contracts.batch import DocumentResult
from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.deid.detect import detect_fields
from doc2tests.generate.population import generate_population
from doc2tests.imagegen.edit import Replacement, edit_form_image
from doc2tests.ingest.loaders import detect_kind
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMProvider

_log = get_logger("batch")


def process_document(
    path: str, provider: LLMProvider, *, n: int = 10, seed: int = 42
) -> DocumentResult:
    """Cheap stages only — no image generation. Errors are captured, not raised, so
    one bad file never aborts a batch."""
    try:
        kind = SourceKind(detect_kind(path))
        st = GraphState(input_ref=InputRef(path=path, kind=kind),
                        config=RunConfig(n=n, seed=seed))
        st = st.model_copy(update=ingest_parse(st, provider))
        st = st.model_copy(update=detect_fields(st))
        st = st.model_copy(update=generate_population(st))
        err = st.errors[0].message if st.errors else None
        page = st.page_images[0] if st.page_images else None
        return DocumentResult(path=path, detected=st.detected,
                              population=st.population, page_image=page, error=err)
    except Exception as exc:  # noqa: BLE001 - one file's failure must not stop the batch
        _log.exception("process_document failed for %s", path)
        return DocumentResult(path=path, error=str(exc))


def process_batch(
    paths: list[str], provider: LLMProvider, *,
    n: int = 10, seed: int = 42, max_workers: int = 4,
) -> list[DocumentResult]:
    """Process many files through the cheap stages. Results keep input order; each
    file gets its own seed offset so identical forms still yield distinct data."""
    _log.info("batch: processing %d document(s), n=%d, workers=%d",
              len(paths), n, max_workers)
    results: list[DocumentResult | None] = [None] * len(paths)

    if max_workers <= 1 or len(paths) <= 1:
        for i, p in enumerate(paths):
            results[i] = process_document(p, provider, n=n, seed=seed + i)
        return [r for r in results if r is not None]

    def work(item: tuple[int, str]) -> tuple[int, DocumentResult]:
        i, p = item
        return i, process_document(p, provider, n=n, seed=seed + i)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for i, res in ex.map(work, list(enumerate(paths))):
            results[i] = res
    return [r for r in results if r is not None]


def render_variant(
    doc: DocumentResult, record_index: int, provider: LLMProvider, doc_hint: str = "",
) -> bytes:
    """The metered, EXPENSIVE step: edit the original image for one variant. Called
    explicitly by the caller so cost stays under control at scale."""
    if doc.page_image is None:
        raise ValueError(f"no page image to edit for {doc.path}")
    rec = doc.population[record_index]
    personal = [d for d in doc.detected if d.is_personal]
    reps = [Replacement(old=d.value, new=rec.values[d.id].value)
            for d in personal if d.id in rec.values]
    return edit_form_image(doc.page_image, reps, provider, doc_hint)

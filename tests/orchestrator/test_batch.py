from unittest.mock import patch

from doc2tests.contracts.batch import DocumentResult
from doc2tests.orchestrator.batch import (
    process_batch,
    process_document,
    render_variant,
)
from doc2tests.providers.base import LLMResponse


class _StubProvider:
    name = "stub"

    def __init__(self):
        self.edit_calls = 0

    def complete_text(self, *a, **k):
        return LLMResponse(text="{}")

    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text='{"raw_text":"t","fields":['
                                '{"label":"מספר זהות","value":"123456782"},'
                                '{"label":"שם","value":"דנה כהן"}]}')

    def edit_image(self, image, prompt, **k):
        self.edit_calls += 1
        return b"EDITED:" + image


def test_process_document_runs_cheap_stages_no_image_call():
    prov = _StubProvider()
    with patch("doc2tests.ingest.parse.rasterize", return_value=[b"IMG"]):
        res = process_document("a.jpeg", prov, n=4)
    assert isinstance(res, DocumentResult)
    assert res.path == "a.jpeg"
    assert res.page_image == b"IMG"
    assert len(res.population) == 4
    assert [d.is_personal for d in res.detected] == [True, True]
    assert prov.edit_calls == 0                 # NO image generation in the cheap stage
    assert res.error is None


def test_process_batch_returns_one_result_per_file_in_order():
    prov = _StubProvider()
    with patch("doc2tests.ingest.parse.rasterize", return_value=[b"IMG"]):
        results = process_batch(["a.jpeg", "b.jpeg", "c.jpeg"], prov, n=2, max_workers=2)
    assert [r.path for r in results] == ["a.jpeg", "b.jpeg", "c.jpeg"]
    assert all(len(r.population) == 2 for r in results)
    assert prov.edit_calls == 0                 # batch data stage never renders images


def test_process_document_records_error_for_bad_path():
    prov = _StubProvider()
    res = process_document("form.txt", prov)   # unsupported kind -> error
    assert res.error is not None
    assert res.population == []


def test_render_variant_is_the_metered_image_call():
    prov = _StubProvider()
    with patch("doc2tests.ingest.parse.rasterize", return_value=[b"IMG"]):
        res = process_document("a.jpeg", prov, n=3)
    img = render_variant(res, 0, prov)
    assert img.startswith(b"EDITED:")
    assert prov.edit_calls == 1                 # exactly one image per explicit call

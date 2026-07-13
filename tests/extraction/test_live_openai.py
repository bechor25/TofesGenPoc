import os

import pytest

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef
from doc2tests.deid.detect import detect_fields
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.openai_provider import OpenAIProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY"
)


def _apply(state, patch):
    return state.model_copy(update=patch)


@pytest.mark.parametrize("fixture", [
    "tests/fixtures/doc2_printed_tax_letter.jpeg",
    "tests/fixtures/doc1_handwritten_bank_form.jpeg",
])
def test_live_extraction_detects_values(fixture):
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    provider = OpenAIProvider(model=model)
    state = GraphState(input_ref=InputRef(path=fixture, kind=SourceKind.image))
    state = _apply(state, ingest_parse(state, provider))
    state = _apply(state, detect_fields(state))
    assert state.errors == [], state.errors
    assert len(state.detected) >= 3
    assert any(d.is_personal for d in state.detected)

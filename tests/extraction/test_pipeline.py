from unittest.mock import patch

from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.deid.detect import detect_fields
from doc2tests.generate.population import generate_population
from doc2tests.ingest.parse import ingest_parse
from doc2tests.providers.base import LLMResponse
from doc2tests.validators import validate


class _FakeVision:
    name = "fake-vision"

    def __init__(self, text):
        self._text = text

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("vision only")

    def extract_vision(self, images, prompt, *, json_mode=False):
        return LLMResponse(text=self._text)

    def edit_image(self, image, prompt, **k):
        return b""


def _apply(state, patch):
    return state.model_copy(update=patch)


def test_extraction_to_valid_population_chain():
    """ingest -> detect -> generate produces N records of VALID personal values."""
    provider = _FakeVision(
        '{"raw_text":"בקשה","fields":['
        '{"label":"מספר זהות","value":"123456782","value_kind":"handwritten"},'
        '{"label":"שם מלא","value":"דנה כהן","value_kind":"printed"},'
        '{"label":"עיר","value":"חיפה","value_kind":"printed"}]}')

    state = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
                       config=RunConfig(n=5, seed=3))
    with patch("doc2tests.ingest.parse.rasterize", return_value=[b"IMG"]):
        state = _apply(state, ingest_parse(state, provider))
    state = _apply(state, detect_fields(state))

    personal = [d for d in state.detected if d.is_personal]
    assert {d.field_type for d in personal} == {FieldType.israeli_id, FieldType.hebrew_name}

    state = _apply(state, generate_population(state))
    assert len(state.population) == 5
    for rec in state.population:
        idv = rec.values[next(d.id for d in personal
                              if d.field_type == FieldType.israeli_id)]
        assert validate(FieldType.israeli_id, idv.value) is True
    assert state.errors == []

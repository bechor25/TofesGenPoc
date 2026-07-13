from doc2tests.contracts.enums import FieldType
from doc2tests.contracts.state import DetectedValue
from doc2tests.generate.data_agent import generate_text_variants
from doc2tests.providers.base import LLMResponse


class _Stub:
    name = "stub"

    def complete_text(self, prompt, *, system=None, json_mode=False):
        return LLMResponse(text='{"fields":{"dx":["דלקת גרון","נזלת חריפה"]}}')

    def extract_vision(self, *a, **k):
        return LLMResponse(text="{}")

    def edit_image(self, *a, **k):
        return b""


def _fld(fid="dx"):
    return DetectedValue(id=fid, label="אבחנה", value="דלקת",
                         field_type=FieldType.free_text, is_personal=True)


def test_returns_realistic_variant_lists():
    out = generate_text_variants([_fld()], "טופס ביקור רפואי", 2, _Stub())
    assert out == {"dx": ["דלקת גרון", "נזלת חריפה"]}


def test_ignores_ids_not_requested():
    class Extra(_Stub):
        def complete_text(self, *a, **k):
            return LLMResponse(text='{"fields":{"dx":["א"],"ghost":["ב"]}}')
    out = generate_text_variants([_fld()], "", 1, Extra())
    assert out == {"dx": ["א"]}          # unknown id dropped


def test_bad_json_returns_empty_for_local_fallback():
    class Bad(_Stub):
        def complete_text(self, *a, **k):
            return LLMResponse(text="not json at all")
    assert generate_text_variants([_fld()], "", 3, Bad()) == {}

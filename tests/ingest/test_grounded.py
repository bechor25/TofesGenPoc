from doc2tests.contracts.enums import ValueKind
from doc2tests.ingest.grounded import Line, extract_grounded, structure, transcribe
from doc2tests.providers.base import LLMResponse

_LINES_JSON = (
    '{"lines":['
    '{"text":"מספר זהות","bbox":{"x":0.6,"y":0.1,"w":0.2,"h":0.03},"kind":"printed"},'
    '{"text":"318885684","bbox":{"x":0.3,"y":0.1,"w":0.15,"h":0.03},"kind":"handwritten"},'
    '{"text":"רשות המסים","bbox":{"x":0.7,"y":0.02,"w":0.25,"h":0.03},"kind":"printed"}]}'
)
_FIELDS_JSON = (
    '{"raw_text":"מספר זהות 318885684",'
    '"fields":[{"label":"מספר זהות","value":"318885684","personal":true,'
    '"value_kind":"handwritten","bbox":{"x":0.3,"y":0.1,"w":0.15,"h":0.03}},'
    '{"label":"רשות","value":"רשות המסים","personal":false,"value_kind":"printed"}]}'
)


class _TwoStageStub:
    """Returns the transcription payload for pass 1 and the structured payload for
    pass 2, distinguished by a marker in each prompt."""
    name = "stub-vl"

    def __init__(self):
        self.vision_calls = 0

    def complete_text(self, *a, **k):
        return LLMResponse(text="{}")

    def extract_vision(self, images, prompt, *, json_mode=False):
        self.vision_calls += 1
        if "TRANSCRIBE" in prompt:
            return LLMResponse(text=_LINES_JSON)
        return LLMResponse(text=_FIELDS_JSON)

    def edit_image(self, *a, **k):
        return b""


def test_transcribe_returns_lines_with_bbox_and_kind():
    lines = transcribe([b"IMG"], _TwoStageStub())
    assert len(lines) == 3
    assert isinstance(lines[0], Line)
    assert lines[1].text == "318885684"
    assert lines[1].kind == ValueKind.handwritten
    assert lines[1].bbox is not None and abs(lines[1].bbox.x - 0.3) < 1e-6


def test_structure_pairs_label_and_value_constrained_to_lines():
    lines = [
        Line(text="מספר זהות", bbox=None, kind=ValueKind.printed),
        Line(text="318885684", bbox=None, kind=ValueKind.handwritten),
    ]
    raw, fields = structure(lines, [b"IMG"], _TwoStageStub())
    assert fields[0].label == "מספר זהות"
    assert fields[0].value == "318885684"
    assert fields[0].value_kind == ValueKind.handwritten
    assert fields[0].personal is True
    assert fields[1].personal is False       # static form content tagged non-personal


def test_extract_grounded_runs_two_passes():
    stub = _TwoStageStub()
    raw, fields = extract_grounded([b"IMG"], stub)
    assert stub.vision_calls == 2          # pass 1 transcribe + pass 2 structure
    assert fields and fields[0].value == "318885684"
    assert "318885684" in raw

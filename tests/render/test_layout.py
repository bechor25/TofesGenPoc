from doc2tests.contracts.enums import FieldType
from doc2tests.contracts.template import Field
from doc2tests.providers.base import LLMResponse
from doc2tests.render.layout import fill_layout, generate_layout_template


def test_fill_layout_substitutes_all_brace_variants():
    for tmpl in ("<td>{{ pid }}</td>", "<td>{{pid}}</td>",
                 "<td>{pid}</td>", "<td>{ pid }</td>"):
        assert fill_layout(tmpl, {"pid": "123456782"}) == "<td>123456782</td>"


def test_fill_layout_empty_value_clears_slot():
    assert fill_layout("<b>{a}</b>", {"a": ""}) == "<b></b>"


def test_fill_layout_escapes_values():
    assert "&lt;x&gt;" in fill_layout("<td>{a}</td>", {"a": "<x>"})


def test_fill_layout_leaves_css_braces_untouched():
    css = "<style>body { margin:0; }</style><td>{pid}</td>"
    out = fill_layout(css, {"pid": "9"})
    assert "body { margin:0; }" in out and ">9<" in out


class _FakeVision:
    name = "fake"

    def __init__(self):
        self.prompt = None

    def complete_text(self, prompt, *, system=None, json_mode=False):
        raise AssertionError("vision only")

    def extract_vision(self, images, prompt, *, json_mode=False):
        self.prompt = prompt
        # model wraps output in a markdown fence + prose
        return LLMResponse(text="Here is the HTML:\n```html\n"
                                '<html dir="rtl"><body>{{ pid }}</body></html>\n```')


def test_generate_layout_strips_fences_and_passes_field_ids():
    prov = _FakeVision()
    fields = [Field(id="pid", label="מספר זהות", type=FieldType.israeli_id)]
    html = generate_layout_template([b"\xff\xd8\xff"], fields, prov)
    assert html.startswith("<html")
    assert html.endswith("</html>")
    assert "```" not in html
    assert "pid: מספר זהות" in prov.prompt      # field mapping fed to the model

from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.template import CanonicalTemplate, DocSource, Field
from doc2tests.render.html import render_html


def _tmpl():
    return CanonicalTemplate(
        doc_type="bank-form", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="pid", label="מספר זהות", type=FieldType.israeli_id)],
    )


def _rec():
    return Record(index=3, test_class="equivalence", expected_valid=True,
                  values={"pid": Value(field_id="pid", value="123456782")})


def test_html_contains_label_value_and_rtl():
    html = render_html(_tmpl(), _rec())
    assert "מספר זהות" in html
    assert "123456782" in html
    assert 'dir="rtl"' in html


def test_html_marks_invalid_values():
    tmpl = _tmpl()
    rec = Record(index=0, test_class="negative", expected_valid=False,
                 violates="israeli_id.invalid",
                 values={"pid": Value(field_id="pid", value="1", valid=False)})
    html = render_html(tmpl, rec)
    assert "invalid" in html.lower()

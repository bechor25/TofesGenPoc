from doc2tests.contracts.enums import FieldType, SourceKind, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.template import BBox, CanonicalTemplate, DocSource, Field
from doc2tests.render.overlay import has_overlay, render_overlay_html

_BG = b"\xff\xd8\xff\xd9"  # tiny fake jpeg


def _tmpl():
    return CanonicalTemplate(
        doc_type="bank-form", source=DocSource(kind=SourceKind.image),
        fields=[
            Field(id="pid", label="מספר זהות", type=FieldType.israeli_id,
                  bbox=BBox(page=1, x=0.6, y=0.34, w=0.15, h=0.03)),
            Field(id="nobox", label="ללא מיקום", type=FieldType.free_text),
        ],
    )


def test_has_overlay_true_when_any_bbox():
    assert has_overlay(_tmpl()) is True


def test_blank_overlay_shows_placeholder_and_background():
    html = render_overlay_html(_tmpl(), _BG)
    assert "data:image/jpeg;base64," in html
    assert "{{ pid }}" in html            # placeholder for the bbox field
    assert 'dir="rtl"' in html
    assert "position:absolute" in html or "fld" in html


def test_filled_overlay_shows_values_and_marks_invalid():
    rec = Record(index=0, test_class=TestClass.negative, expected_valid=False,
                 violates="israeli_id.invalid",
                 values={"pid": Value(field_id="pid", value="1", valid=False)})
    html = render_overlay_html(_tmpl(), _BG, rec)
    assert ">1</div>" in html
    assert "bad" in html                  # invalid value styled
    assert "INVALID" in html


def test_field_without_bbox_is_skipped():
    html = render_overlay_html(_tmpl(), _BG)
    assert "ללא מיקום" not in html  # nobox field has no placement -> not drawn

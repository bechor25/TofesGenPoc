from doc2tests.contracts.enums import FieldType, RenderStrategy, SourceKind, ValueKind
from doc2tests.contracts.state import DetectedField, GraphState, InputRef
from doc2tests.contracts.template import BBox
from doc2tests.template.build import build_template


def _state(detected):
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        detected_fields=detected,
    )


def test_build_assigns_slugs_and_constraints():
    st = _state([
        DetectedField(label="Primary Applicant ID", value="123456782",
                      type=FieldType.israeli_id, pii=True, value_kind=ValueKind.handwritten),
    ])
    out = build_template(st)
    tmpl = out["template"]
    f = tmpl.fields[0]
    assert f.id == "primary_applicant_id"
    assert f.placeholder == "{{ primary_applicant_id }}"
    assert f.constraints.checksum == "israeli_id"
    assert f.constraints.length == 9
    assert f.constraints.required is True


def test_duplicate_labels_get_unique_ids():
    st = _state([
        DetectedField(label="מספר זהות", value="123456782", type=FieldType.israeli_id),
        DetectedField(label="מספר זהות", value="318444973", type=FieldType.israeli_id),
    ])
    ids = [f.id for f in build_template(st)["template"].fields]
    assert len(ids) == len(set(ids))


def test_render_strategy_overlay_when_bbox_present():
    st = _state([
        DetectedField(label="שם", value="כהן", type=FieldType.hebrew_name,
                      bbox=BBox(page=1, x=0.1, y=0.1, w=0.2, h=0.03)),
    ])
    assert build_template(st)["template"].source.render_strategy == RenderStrategy.overlay


def test_render_strategy_reconstruct_when_no_bbox():
    st = _state([DetectedField(label="שם", value="כהן", type=FieldType.hebrew_name)])
    assert build_template(st)["template"].source.render_strategy == RenderStrategy.reconstruct

import json

from doc2tests.contracts.enums import (
    FieldType,
    PiiType,
    RelationOp,
    RenderStrategy,
    SourceKind,
    ValueKind,
)
from doc2tests.contracts.template import (
    BBox,
    CanonicalTemplate,
    Constraints,
    DocSource,
    Field,
    LayoutBlock,
    Relation,
)


def _sample_template() -> CanonicalTemplate:
    return CanonicalTemplate(
        doc_type="bank-eligibility-transfer",
        source=DocSource(kind=SourceKind.image, pages=1,
                         render_strategy=RenderStrategy.reconstruct),
        layout_blocks=[LayoutBlock(id="b1", kind="field", page=1,
                                   bbox=BBox(page=1, x=0.6, y=0.34, w=0.15, h=0.03))],
        fields=[
            Field(
                id="primary_applicant_id",
                label="מספר זהות (מבקש ראשי)",
                type=FieldType.israeli_id,
                value_kind=ValueKind.handwritten,
                pii=True, pii_type=PiiType.IL_ID,
                constraints=Constraints(required=True, checksum="israeli_id", length=9),
                placeholder="{{ primary_applicant_id }}",
                bbox=BBox(page=1, x=0.6, y=0.34, w=0.15, h=0.03),
            ),
            Field(id="entry_date", label="תאריך כניסה", type=FieldType.date,
                  placeholder="{{ entry_date }}"),
            Field(id="contract_date", label="תאריך חוזה", type=FieldType.date,
                  placeholder="{{ contract_date }}"),
        ],
        relations=[Relation(kind="order", op=RelationOp.le,
                            left="contract_date", right="entry_date")],
    )


def test_template_roundtrips_through_json():
    t = _sample_template()
    dumped = t.model_dump_json()
    reloaded = CanonicalTemplate.model_validate_json(dumped)
    assert reloaded == t
    assert json.loads(dumped)["fields"][0]["type"] == "israeli_id"


def test_field_ids_must_be_unique():
    import pytest
    from pydantic import ValidationError
    t = _sample_template()
    data = t.model_dump()
    data["fields"].append(data["fields"][0])  # duplicate id
    with pytest.raises(ValidationError):
        CanonicalTemplate.model_validate(data)


def test_relation_endpoints_must_reference_existing_fields():
    import pytest
    from pydantic import ValidationError
    data = _sample_template().model_dump()
    data["relations"][0]["right"] = "no_such_field"
    with pytest.raises(ValidationError):
        CanonicalTemplate.model_validate(data)


def test_placeholder_defaults_to_field_id():
    f = Field(id="foo", label="Foo", type=FieldType.free_text)
    assert f.placeholder == "{{ foo }}"


def test_bbox_is_optional():
    f = Field(id="x", label="X", type=FieldType.free_text)
    assert f.bbox is None

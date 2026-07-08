from doc2tests.contracts.enums import (
    FieldType,
    PiiType,
    RelationOp,
    RenderStrategy,
    SourceKind,
    TestClass,
)


def test_field_type_has_semantic_types():
    values = {t.value for t in FieldType}
    assert {"hebrew_name", "israeli_id", "date", "gush_helka", "assessment_number",
            "bank_branch", "address", "phone", "currency", "enum", "free_text"} <= values


def test_test_class_three_members():
    assert [c.value for c in TestClass] == ["equivalence", "boundary", "negative"]


def test_enums_are_str():
    assert FieldType.israeli_id == "israeli_id"
    assert PiiType.IL_ID == "IL_ID"
    assert SourceKind.image == "image"
    assert RenderStrategy.reconstruct == "reconstruct"
    assert RelationOp.le == "<="

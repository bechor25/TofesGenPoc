from doc2tests.contracts.enums import FieldType, PiiType, SourceKind, ValueKind


def test_enum_members_present():
    assert FieldType.israeli_id == "israeli_id"
    assert PiiType.IL_ID == "IL_ID"
    assert set(SourceKind) == {SourceKind.image, SourceKind.pdf, SourceKind.docx}
    assert ValueKind.handwritten == "handwritten"

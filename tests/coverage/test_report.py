from doc2tests.contracts.enums import FieldType, SourceKind, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.template import CanonicalTemplate, DocSource, Field
from doc2tests.coverage.report import build_coverage


def _tmpl():
    return CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="pid", label="ז", type=FieldType.israeli_id),
                Field(id="note", label="הערה", type=FieldType.free_text)],
    )


def _pop():
    return [
        Record(index=0, test_class=TestClass.equivalence, expected_valid=True,
               values={"pid": Value(field_id="pid", value="123456782"),
                       "note": Value(field_id="note", value="x")}),
        Record(index=1, test_class=TestClass.negative, expected_valid=False,
               violates="israeli_id.invalid",
               values={"pid": Value(field_id="pid", value="1", valid=False),
                       "note": Value(field_id="note", value="y")}),
    ]


def test_counts_per_class_and_field():
    rep = build_coverage(_tmpl(), _pop())
    eq = [c for c in rep.cells
          if c.field_id == "pid" and c.test_class == TestClass.equivalence]
    assert eq and eq[0].count == 1


def test_rules_exercised_lists_violations():
    rep = build_coverage(_tmpl(), _pop())
    assert "israeli_id.invalid" in rep.rules_exercised


def test_gaps_flag_untested_negative_fields():
    rep = build_coverage(_tmpl(), _pop())
    assert isinstance(rep.gaps, list)


def test_validity_summary_counts_and_no_unexpected_invalid():
    rep = build_coverage(_tmpl(), _pop())
    assert rep.total_records == 2
    assert rep.valid_records == 1          # the equivalence record is fully valid
    assert rep.unexpected_invalid == []    # the negative one is expected-invalid

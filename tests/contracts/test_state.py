from doc2tests.contracts.enums import SourceKind, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import (
    GraphState,
    InputRef,
    RunConfig,
    StageError,
)


def test_record_carries_class_and_validity():
    rec = Record(
        index=0,
        test_class=TestClass.negative,
        expected_valid=False,
        violates="israeli_id.checksum",
        values={"primary_applicant_id": Value(field_id="primary_applicant_id",
                                              value="123456789", valid=False)},
    )
    assert rec.expected_valid is False
    assert rec.values["primary_applicant_id"].value == "123456789"


def test_runconfig_defaults():
    cfg = RunConfig()
    assert cfg.n == 100
    assert abs(cfg.mix[TestClass.equivalence] + cfg.mix[TestClass.boundary]
               + cfg.mix[TestClass.negative] - 1.0) < 1e-9
    assert cfg.formats == ["html", "docx"]


def test_graphstate_minimal_construction():
    st = GraphState(
        input_ref=InputRef(path="tests/fixtures/doc2.jpeg", kind=SourceKind.image),
        config=RunConfig(n=10),
    )
    assert st.population == []
    assert st.errors == []
    assert st.template is None


def test_stage_error_records_stage():
    e = StageError(stage="ingest_parse", message="vision timeout")
    assert e.stage == "ingest_parse"

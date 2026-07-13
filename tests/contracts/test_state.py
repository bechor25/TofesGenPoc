from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.state import (
    DetectedValue,
    GraphState,
    InputRef,
    ReviewDecision,
    RunConfig,
)


def test_graphstate_defaults():
    st = GraphState(input_ref=InputRef(path="x.jpeg", kind=SourceKind.image))
    assert st.config.n == 10
    assert st.detected == [] and st.population == [] and st.output_images == []


def test_review_decision_carries_values():
    dv = DetectedValue(id="pid", label="ת.ז", value="1", field_type=FieldType.israeli_id,
                       is_personal=True)
    rd = ReviewDecision(approved=True, values=[dv])
    assert rd.values[0].id == "pid"


def test_runconfig_overrides():
    assert RunConfig(n=25, seed=1).n == 25

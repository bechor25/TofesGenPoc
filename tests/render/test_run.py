import os

from doc2tests.contracts.enums import FieldType, SourceKind, TestClass
from doc2tests.contracts.records import Record, Value
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.contracts.template import CanonicalTemplate, DocSource, Field
from doc2tests.render.run import render_fill


def _state(formats):
    tmpl = CanonicalTemplate(
        doc_type="d", source=DocSource(kind=SourceKind.image),
        fields=[Field(id="pid", label="מספר זהות", type=FieldType.israeli_id)],
    )
    pop = [Record(index=0, test_class=TestClass.equivalence, expected_valid=True,
                  values={"pid": Value(field_id="pid", value="123456782")})]
    return GraphState(
        input_ref=InputRef(path="x.jpeg", kind=SourceKind.image),
        template=tmpl, population=pop, config=RunConfig(formats=formats),
    )


def test_render_fill_writes_both_formats(tmp_path):
    out = render_fill(_state(["html", "docx"]), str(tmp_path))
    docs = out["outputs"]
    assert {d.fmt for d in docs} == {"html", "docx"}
    for d in docs:
        assert os.path.exists(d.path)


def test_render_fill_html_only(tmp_path):
    out = render_fill(_state(["html"]), str(tmp_path))
    assert {d.fmt for d in out["outputs"]} == {"html"}

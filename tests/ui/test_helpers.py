import io
import zipfile

from doc2tests.contracts.records import Record, Value
from doc2tests.ui.helpers import records_to_rows, zip_images


def test_zip_images_returns_zip_bytes():
    data = zip_images([b"AAA", b"BBB"], prefix="form")
    assert data[:2] == b"PK"                       # zip magic
    zf = zipfile.ZipFile(io.BytesIO(data))
    assert sorted(zf.namelist()) == ["form_1.png", "form_2.png"]


def test_records_to_rows_flattens_values():
    recs = [Record(index=0, values={"pid": Value(field_id="pid", value="123")})]
    rows = records_to_rows(recs)
    assert rows == [{"#": 1, "pid": "123"}]

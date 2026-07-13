import pytest

from doc2tests.ingest.loaders import detect_kind


def test_detect_kind_by_extension():
    assert detect_kind("a.jpg") == "image"
    assert detect_kind("a.PNG") == "image"
    assert detect_kind("a.pdf") == "pdf"
    assert detect_kind("a.docx") == "docx"


def test_detect_kind_rejects_unknown():
    with pytest.raises(ValueError):
        detect_kind("a.txt")

import pytest

from doc2tests.common.json_utils import extract_json


def test_plain_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_strips_code_fence():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_ignores_prose_around_object():
    assert extract_json('Here you go:\n{"a": [1, 2]}\nThanks') == {"a": [1, 2]}


def test_handles_nested_braces():
    assert extract_json('{"a": {"b": 1}}') == {"a": {"b": 1}}


def test_raises_on_no_object():
    with pytest.raises(ValueError):
        extract_json("no json here")

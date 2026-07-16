import pytest

from doc2tests.db import repo


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'archive.db'}")
    repo.reset()
    yield
    repo.reset()


def test_save_source_and_generated_then_list(sqlite_db):
    sid = repo.save_source("form.pdf", b"IMGBYTES", "טופs ביקור רפואי")
    assert sid is not None
    gid = repo.save_generated(sid, 0, {"שם": "דנה כהן"}, b"PNGA")
    repo.save_generated(sid, 1, {"שם": "רון לוי"}, b"PNGB")
    assert gid is not None

    sources = repo.list_sources()
    assert len(sources) == 1
    assert sources[0].id == sid
    assert sources[0].n_generated == 2

    gens = repo.list_generated(sid)
    assert [g.variant_index for g in gens] == [0, 1]
    assert gens[0].values["שם"] == "דנה כהן"
    assert repo.get_image(gid) == b"PNGA"


def test_source_dedupes_by_content_hash(sqlite_db):
    a = repo.save_source("a.pdf", b"SAME", "")
    b = repo.save_source("b.pdf", b"SAME", "summary")   # same bytes -> same source
    assert a == b


def test_generated_upsert_replaces_same_variant(sqlite_db):
    sid = repo.save_source("x.pdf", b"IMG", "")
    g1 = repo.save_generated(sid, 0, {"a": "1"}, b"OLD")
    g2 = repo.save_generated(sid, 0, {"a": "2"}, b"NEW")   # same (source, variant)
    assert g1 == g2
    assert repo.get_image(g1) == b"NEW"
    assert repo.list_generated(sid)[0].values["a"] == "2"


def test_get_source_and_set_extraction(sqlite_db):
    sid = repo.save_source("form.pdf", b"IMGBYTES", "summary")
    full = repo.get_source(sid)
    assert full is not None
    assert full.page_image == b"IMGBYTES"
    assert full.detected is None  # not extracted yet

    repo.set_extraction(sid, "better summary",
                        [{"id": "a", "label": "שם", "value": "דנה"}])
    full2 = repo.get_source(sid)
    assert full2 is not None
    assert full2.detected is not None
    assert full2.detected[0]["label"] == "שם"
    assert full2.doc_summary == "better summary"

    row = repo.list_sources()[0]
    assert row.has_page_image is True
    assert row.has_detected is True


def test_list_flags_false_before_extraction(sqlite_db):
    repo.save_source("x.pdf", b"IMG", "")
    row = repo.list_sources()[0]
    assert row.has_page_image is True
    assert row.has_detected is False


def test_get_source_missing_returns_none(sqlite_db):
    assert repo.get_source(999) is None


def test_add_generated_accumulates_with_difficulty(sqlite_db):
    sid = repo.save_source("f.pdf", b"IMG", "")
    a = repo.add_generated(sid, 3, {"x": "1"}, b"A")
    b = repo.add_generated(sid, 3, {"x": "2"}, b"B")
    c = repo.add_generated(sid, 10, {"x": "3"}, b"C")
    assert a and b and c and a != b != c

    gens = repo.list_generated(sid)
    assert len(gens) == 3
    assert [g.variant_index for g in gens] == [0, 1, 2]  # running counter, accumulates
    assert {g.difficulty for g in gens} == {3, 10}

    # filter by difficulty
    assert len(repo.list_generated(sid, difficulty=3)) == 2
    assert len(repo.list_generated(sid, difficulty=10)) == 1
    assert repo.list_generated_images(sid, difficulty=10) == [b"C"]
    assert len(repo.list_generated_images(sid)) == 3
    assert repo.list_difficulties(sid) == [3, 10]


def test_disabled_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    repo.reset()
    assert repo.available() is False
    assert repo.save_source("x", b"y") is None
    assert repo.save_generated(1, 0, {}, b"z") is None
    assert repo.list_sources() == []
    assert repo.get_image(1) is None
    repo.reset()

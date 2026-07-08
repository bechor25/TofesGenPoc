from doc2tests.common.slug import slugify, unique_slug


def test_ascii_lowercase_underscores():
    assert slugify("Primary Applicant ID") == "primary_applicant_id"


def test_hebrew_label_falls_back_to_transliteration_marker():
    # non-ascii label yields a non-empty ascii slug
    s = slugify("מספר זהות")
    assert s and all(c.isalnum() or c == "_" for c in s)


def test_hebrew_slug_is_deterministic():
    assert slugify("מספר זהות") == slugify("מספר זהות")


def test_unique_slug_disambiguates_collisions():
    seen = {"entry_date"}
    assert unique_slug("Entry Date", seen) == "entry_date_2"
    seen.add("entry_date_2")
    assert unique_slug("Entry Date", seen) == "entry_date_3"


def test_empty_label_gets_field_prefix():
    assert slugify("").startswith("field")

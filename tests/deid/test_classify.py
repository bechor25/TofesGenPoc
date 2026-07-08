from doc2tests.contracts.enums import FieldType, PiiType
from doc2tests.deid.classify import classify_value


def test_valid_israeli_id_detected():
    ft, pii, pii_type = classify_value("מספר זהות", "123456782")
    assert ft == FieldType.israeli_id
    assert pii is True
    assert pii_type == PiiType.IL_ID


def test_id_label_wins_over_ocr_broken_checksum():
    # real handwritten id from the bank form; a misread digit fails the checksum,
    # but the label "מספר זהות" still identifies it as an ID field.
    ft, pii, _ = classify_value("מספר זהות (מבקש ראשי)", "318885684")
    assert ft == FieldType.israeli_id
    assert pii is True


def test_bare_valid_id_without_label():
    ft, _, _ = classify_value("", "123456782")
    assert ft == FieldType.israeli_id


def test_date_detected():
    ft, _, _ = classify_value("תאריך כניסה", "31.10.21")
    assert ft == FieldType.date


def test_gush_helka_detected_by_label():
    ft, _, _ = classify_value("גוש חלקה", "9007-12-0")
    assert ft == FieldType.gush_helka


def test_phone_detected():
    ft, _, _ = classify_value("טלפון", "04-6327888")
    assert ft == FieldType.phone


def test_hebrew_name_by_label_keyword():
    ft, pii, _ = classify_value("שם משפחה", "כהן")
    assert ft == FieldType.hebrew_name
    assert pii is True


def test_default_free_text():
    ft, pii, _ = classify_value("הערות", "בקשה כללית")
    assert ft == FieldType.free_text
    assert pii is False

from doc2tests.ingest.ocr_boxes import WordBox, group_lines
from doc2tests.template.anchor import anchor_field_bbox


def test_group_lines_clusters_by_y_and_orders_rtl():
    boxes = [
        WordBox("זהות", x=0.70, y=0.30, w=0.08, h=0.02),
        WordBox("מספר", x=0.80, y=0.305, w=0.08, h=0.02),
        WordBox("שם", x=0.80, y=0.50, w=0.08, h=0.02),
    ]
    lines = group_lines(boxes)
    assert len(lines) == 2
    # first line ordered right->left: "מספר" (x=0.80) before "זהות" (x=0.70)
    assert [w.text for w in lines[0]] == ["מספר", "זהות"]


def test_anchor_places_value_left_of_label_rtl():
    # label "מספר זהות" on the right; value area is the gap to its left
    line = [
        WordBox("מספר", x=0.80, y=0.30, w=0.08, h=0.025),
        WordBox("זהות", x=0.70, y=0.30, w=0.08, h=0.025),
    ]
    bb = anchor_field_bbox("מספר זהות", [line])
    assert bb is not None
    assert bb.x < 0.70                    # value sits left of the label
    assert bb.x + bb.w <= 0.70 + 1e-6     # does not overlap the label
    assert abs(bb.y - 0.30) < 0.01
    assert bb.w > 0


def test_anchor_returns_none_when_label_absent():
    line = [WordBox("כתובת", x=0.8, y=0.3, w=0.1, h=0.02)]
    assert anchor_field_bbox("מספר זהות", [line]) is None


def test_anchor_matches_partial_label_tokens():
    line = [
        WordBox("תאריך", x=0.85, y=0.4, w=0.09, h=0.02),
        WordBox("כניסה", x=0.74, y=0.4, w=0.09, h=0.02),
        WordBox("לדירה", x=0.63, y=0.4, w=0.09, h=0.02),
    ]
    bb = anchor_field_bbox("תאריך כניסה לדירה", [line])
    assert bb is not None

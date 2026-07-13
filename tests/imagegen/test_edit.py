from unittest.mock import MagicMock

from doc2tests.imagegen.edit import Replacement, build_edit_prompt, edit_form_image


def test_prompt_lists_every_replacement_and_fidelity_clause():
    reps = [Replacement(old="123456782", new="204685624"),
            Replacement(old="דנה כהן", new="יוסי לוי")]
    prompt = build_edit_prompt(reps, doc_hint="ביטוח לאומי")
    assert "123456782" in prompt and "204685624" in prompt
    assert "דנה כהן" in prompt and "יוסי לוי" in prompt
    assert "ביטוח לאומי" in prompt
    # fidelity intent is explicit
    assert "only" in prompt.lower()


def test_prompt_skips_empty_or_unchanged():
    reps = [Replacement(old="", new="x"), Replacement(old="a", new="a")]
    prompt = build_edit_prompt(reps)
    # no replacement line rendered for empty-old or old==new
    assert "→" not in prompt


def test_edit_form_image_calls_provider_edit():
    prov = MagicMock()
    prov.edit_image.return_value = b"EDITED"
    reps = [Replacement(old="123456782", new="204685624")]
    out = edit_form_image(b"ORIGINAL", reps, prov, doc_hint="form")
    assert out == b"EDITED"
    args = prov.edit_image.call_args
    assert args.args[0] == b"ORIGINAL"
    assert "204685624" in args.args[1]

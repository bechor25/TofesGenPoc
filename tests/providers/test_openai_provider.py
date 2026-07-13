from doc2tests.providers.openai_provider import OpenAIProvider


class _FakeCompletions:
    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)

        class _Msg:
            content = '{"ok": true}'

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

            def model_dump(self):
                return {"model": kwargs["model"]}

        return _Resp()


class _FakeChat:
    def __init__(self, recorder):
        self.completions = _FakeCompletions(recorder)


class _FakeClient:
    def __init__(self, recorder):
        self.chat = _FakeChat(recorder)


def test_complete_text_returns_content():
    rec: dict = {}
    p = OpenAIProvider(model="gpt-4o", client=_FakeClient(rec))
    resp = p.complete_text("hello", system="be brief")
    assert resp.text == '{"ok": true}'
    assert rec["model"] == "gpt-4o"
    assert rec["messages"][0]["role"] == "system"


def test_extract_vision_embeds_image_as_data_uri():
    rec: dict = {}
    p = OpenAIProvider(model="gpt-4o", client=_FakeClient(rec))
    p.extract_vision([b"\xff\xd8\xff"], "read this", json_mode=True)
    content = rec["messages"][-1]["content"]
    image_parts = [c for c in content if c["type"] == "image_url"]
    assert image_parts and image_parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert image_parts[0]["image_url"]["detail"] == "high"   # full-res OCR
    assert rec["response_format"] == {"type": "json_object"}
    assert rec["temperature"] == 0.0                          # deterministic


def test_complete_text_is_deterministic():
    rec: dict = {}
    p = OpenAIProvider(model="gpt-4o", client=_FakeClient(rec))
    p.complete_text("hi")
    assert rec["temperature"] == 0.0


def _mock_edit_client():
    import base64
    from unittest.mock import MagicMock
    returned = base64.b64encode(b"EDITED").decode("ascii")
    client = MagicMock()
    client.images.edit.return_value = MagicMock(data=[MagicMock(b64_json=returned)])
    return client


def test_edit_image_gpt_image_2_omits_input_fidelity():
    client = _mock_edit_client()
    prov = OpenAIProvider(model="gpt-4o", client=client, image_model="gpt-image-2")
    out = prov.edit_image(b"\x89PNG\r\n\x1a\nORIGINAL", "replace values")

    assert out == b"EDITED"
    kwargs = client.images.edit.call_args.kwargs
    assert kwargs["model"] == "gpt-image-2"
    assert "input_fidelity" not in kwargs   # gpt-image-2 rejects this param
    assert kwargs["prompt"] == "replace values"


def test_edit_image_gpt_image_1_sends_input_fidelity_high():
    client = _mock_edit_client()
    prov = OpenAIProvider(model="gpt-4o", client=client, image_model="gpt-image-1")
    prov.edit_image(b"png", "replace values")

    kwargs = client.images.edit.call_args.kwargs
    assert kwargs["model"] == "gpt-image-1"
    assert kwargs["input_fidelity"] == "high"

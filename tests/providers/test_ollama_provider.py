from doc2tests.providers.ollama_provider import OllamaProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.last_url = None
        self.last_json = None

    def post(self, url, json, timeout):
        self.last_url = url
        self.last_json = json
        return _FakeResponse(self._payload)


def test_complete_text_hits_generate_endpoint():
    sess = _FakeSession({"response": "shalom"})
    p = OllamaProvider(model="qwen2.5:7b", host="http://localhost:11434", session=sess)
    resp = p.complete_text("hi", json_mode=True)
    assert resp.text == "shalom"
    assert sess.last_url.endswith("/api/generate")
    assert sess.last_json["model"] == "qwen2.5:7b"
    assert sess.last_json["format"] == "json"
    assert sess.last_json["stream"] is False


def test_extract_vision_passes_base64_images():
    sess = _FakeSession({"response": "{}"})
    p = OllamaProvider(model="llava", host="http://localhost:11434", session=sess)
    p.extract_vision([b"\xff\xd8\xff"], "read")
    assert isinstance(sess.last_json["images"], list) and sess.last_json["images"]

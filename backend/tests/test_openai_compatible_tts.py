from app.providers.adapters import CustomHTTPAdapter
from app.providers.base import ProviderConfig, ProviderFailure


class FakeResponse:
    def __init__(self, content=b"ID3-audio", content_type="audio/mpeg", status=200):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.content = content

    def iter_content(self, chunk_size=65536):
        yield self.content

    def close(self):
        pass


def config(extra=None):
    return ProviderConfig(
        id="openrouter-tts",
        name="OpenRouter Fish",
        kind="tts",
        adapter="custom_http",
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="fish-audio/s2.1-pro-free:free",
        temperature=None,
        max_tokens=None,
        streaming=False,
        config={"voice": "fish-voice-id", **(extra or {})},
    )


def test_custom_http_tts_requests_browser_playable_mp3_by_default(app, monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        audio, media_type = CustomHTTPAdapter(config()).synthesize("Salam dünya", None)

    assert audio == b"ID3-audio"
    assert media_type == "audio/mpeg"
    assert captured["url"] == "https://openrouter.ai/api/v1/audio/speech"
    assert captured["json"] == {
        "model": "fish-audio/s2.1-pro-free:free",
        "input": "Salam dünya",
        "voice": "fish-voice-id",
        "response_format": "mp3",
    }


def test_custom_http_tts_rejects_non_audio_success_response(app, monkeypatch):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse(b'{"error":"bad"}', "application/json"),
    )
    with app.app_context():
        try:
            CustomHTTPAdapter(config()).synthesize("Salam", None)
        except ProviderFailure as error:
            assert error.code == "provider_malformed_response"
        else:
            raise AssertionError("non-audio TTS response should be rejected")

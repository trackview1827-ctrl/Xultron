import json

from app.providers.adapters import ElevenLabsAdapter
from app.providers.base import ProviderConfig, ProviderFailure
from tests.conftest import post_json


class FakeResponse:
    def __init__(self, payload, status=200, content_type="application/json"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"
        self.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield self.content

    def close(self):
        self.closed = True


def eleven_config(kind="tts", model=None, config=None):
    return ProviderConfig(
        id="eleven-test",
        name="ElevenLabs",
        kind=kind,
        adapter="elevenlabs",
        base_url="https://api.elevenlabs.io/v1",
        api_key="test-eleven-key",
        model=model,
        temperature=None,
        max_tokens=None,
        streaming=False,
        config=config or {},
    )


def test_elevenlabs_tts_uses_native_auth_and_voice(app, monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse(b"ID3-audio", content_type="audio/mpeg")

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        audio, media_type = ElevenLabsAdapter(eleven_config(config={"voice": "voice/one", "outputFormat": "mp3_22050_32", "speed": 1.1})).synthesize("Salam dünya", None)

    assert audio == b"ID3-audio"
    assert media_type == "audio/mpeg"
    assert captured["url"].endswith("/text-to-speech/voice%2Fone")
    assert captured["params"] == {"output_format": "mp3_22050_32"}
    assert captured["headers"]["xi-api-key"] == "test-eleven-key"
    assert "test-eleven-key" not in captured["url"]
    assert captured["json"] == {"text": "Salam dünya", "model_id": "eleven_multilingual_v2", "voice_settings": {"speed": 1.1}}


def test_elevenlabs_stt_posts_file_and_returns_language(app, monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse({"text": "Salam, dünya", "language_code": "az"})

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        result = ElevenLabsAdapter(eleven_config("stt", "scribe_v2")).transcribe(b"audio", "voice.webm", "az")

    assert result == {"text": "Salam, dünya", "language": "az"}
    assert captured["url"] == "https://api.elevenlabs.io/v1/speech-to-text"
    assert captured["headers"] == {"xi-api-key": "test-eleven-key"}
    assert captured["data"] == {"model_id": "scribe_v2", "language_code": "az"}
    assert captured["files"]["file"] == ("voice.webm", b"audio")


def test_elevenlabs_filters_marker_only_non_speech(app, monkeypatch):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse({"text": "[MUZIK CALIYO4]", "language_code": "tr"}),
    )
    with app.app_context():
        result = ElevenLabsAdapter(eleven_config("stt", "scribe_v2")).transcribe(b"audio", "voice.webm", "tr")
    assert result == {"text": "", "language": "tr"}


def test_elevenlabs_models_filter_tts_capability(app, monkeypatch):
    payload = [
        {"model_id": "eleven_multilingual_v2", "name": "Multilingual v2", "can_do_text_to_speech": True},
        {"model_id": "scribe_v2", "name": "Scribe v2", "can_do_text_to_speech": False},
    ]
    monkeypatch.setattr("app.providers.adapters.requests.get", lambda *args, **kwargs: FakeResponse(payload))
    with app.app_context():
        models = ElevenLabsAdapter(eleven_config("tts")).models()
    assert models == [{"id": "eleven_multilingual_v2", "label": "Multilingual v2"}]


def test_elevenlabs_stt_models_are_local_and_base_url_is_pinned(app, monkeypatch):
    monkeypatch.setattr("app.providers.adapters.requests.get", lambda *args, **kwargs: FakeResponse([]))
    with app.app_context():
        assert ElevenLabsAdapter(eleven_config("stt")).models() == [
            {"id": "scribe_v2", "label": "ElevenLabs scribe_v2"},
            {"id": "scribe_v1", "label": "ElevenLabs scribe_v1"},
        ]
        invalid = eleven_config(config={"voice": "x"})
        invalid.base_url = "https://evil.example/v1"
        with __import__("pytest").raises(ProviderFailure):
            ElevenLabsAdapter(invalid).base


def test_elevenlabs_provider_is_voice_only(user_client):
    response = post_json(user_client, "/api/v1/providers", {
        "name": "Wrong ElevenLabs",
        "kind": "ai",
        "adapter": "elevenlabs",
        "baseUrl": "https://api.elevenlabs.io/v1",
        "model": "eleven_multilingual_v2",
    })
    assert response.status_code == 422

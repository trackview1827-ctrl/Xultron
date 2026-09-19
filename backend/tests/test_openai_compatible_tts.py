import pytest

from app.providers.adapters import CustomHTTPAdapter
from app.providers.base import ProviderConfig, ProviderFailure
from tests.conftest import post_json


class FakeResponse:
    def __init__(
        self,
        content=b"ID3-audio\xff\xfb\x90\x64encoded",
        content_type="audio/mpeg",
        status=200,
    ):
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

    assert audio == b"ID3-audio\xff\xfb\x90\x64encoded"
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


def test_custom_http_tts_rejects_json_mislabeled_as_audio(app, monkeypatch):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse(b'{"error":"not audio"}', "audio/mpeg"),
    )
    with app.app_context(), pytest.raises(ProviderFailure) as raised:
        CustomHTTPAdapter(config()).synthesize("Salam", None)
    assert raised.value.code == "provider_malformed_response"


@pytest.mark.parametrize(
    "payload", [b"Internal Server Error", b"\xef\xbb\xbf provider failed"]
)
def test_custom_http_tts_rejects_text_mislabeled_as_raw_audio(
    app, monkeypatch, payload
):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse(payload, "audio/pcm"),
    )
    with app.app_context(), pytest.raises(ProviderFailure) as raised:
        CustomHTTPAdapter(config({"responseFormat": "pcm"})).synthesize("Salam", None)
    assert raised.value.code == "provider_malformed_response"


def test_custom_http_tts_rejects_mime_and_requested_format_mismatch(
    app, monkeypatch
):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse(
            b"RIFF\x04\x00\x00\x00WAVEencoded", "audio/wav"
        ),
    )
    with app.app_context(), pytest.raises(ProviderFailure) as raised:
        CustomHTTPAdapter(config({"responseFormat": "mp3"})).synthesize("Salam", None)
    assert raised.value.code == "provider_malformed_response"


@pytest.mark.parametrize(
    "response_format,content_type",
    [
        ("pcm", "audio/basic"),
    ],
)
def test_custom_http_tts_rejects_raw_audio_subtype_mismatch(
    app, monkeypatch, response_format, content_type
):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse(
            b"\x00\x01\x80\xff" * 32, content_type
        ),
    )
    with app.app_context(), pytest.raises(ProviderFailure) as raised:
        CustomHTTPAdapter(config({"responseFormat": response_format})).synthesize(
            "Salam", None
        )
    assert raised.value.code == "provider_malformed_response"


@pytest.mark.parametrize(
    ("response_format", "content_type", "audio"),
    [
        ("mp3", "audio/mpeg", b"\xff\xfb\x90\x64encoded"),
        ("wav", "audio/wav", b"RIFF\x04\x00\x00\x00WAVEencoded"),
        ("opus", "audio/ogg", b"OggSencoded"),
        ("aac", "audio/aac", b"\xff\xf1encoded"),
        ("flac", "audio/flac", b"fLaCencoded"),
        ("pcm", "audio/pcm", b"\x00\x01\x80\xff" * 32),
    ],
)
def test_custom_http_tts_accepts_supported_audio_signatures(
    app, monkeypatch, response_format, content_type, audio
):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse(audio, content_type),
    )
    with app.app_context():
        result, media_type = CustomHTTPAdapter(
            config({"responseFormat": response_format})
        ).synthesize("Salam", None)
    assert result == audio
    assert media_type == content_type


def test_voice_synthesize_public_api_rejects_mislabeled_provider_audio(
    user_client, monkeypatch
):
    provider = post_json(
        user_client,
        "/api/v1/providers",
        {
            "name": "Boundary TTS",
            "kind": "tts",
            "adapter": "custom_http",
            "baseUrl": "https://provider.example/v1",
            "apiKey": "test-key-1234567890",
            "model": "tts-test",
            "enabled": True,
            "isDefault": True,
            "config": {"responseFormat": "mp3"},
        },
    )
    assert provider.status_code == 201
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse(b'{"error":"not audio"}', "audio/mpeg"),
    )

    response = post_json(user_client, "/api/v1/voice/synthesize", {"text": "Salam"})

    assert response.status_code == 502
    assert response.is_json
    assert response.content_type == "application/json"
    assert response.get_json()["error"]["code"] == "provider_malformed_response"

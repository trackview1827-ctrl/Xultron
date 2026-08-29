import json
from types import SimpleNamespace

from app.providers.adapters import WhisperCppAdapter
from app.providers.base import ProviderConfig, ProviderFailure


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.headers = {"Content-Type": "application/json"}
        self.encoding = "utf-8"
        self.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def iter_content(self, chunk_size=65536):
        yield self.content

    def close(self):
        pass


def config():
    return ProviderConfig("local", "whisper.cpp", "stt", "whisper_cpp", "http://127.0.0.1:8766", None, "tiny", None, None, False, {})


def test_whisper_cpp_transcribes_without_auth(app, monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse({"text": "Merhaba dünya"})

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        result = WhisperCppAdapter(config()).transcribe(b"RIFF\x00\x00\x00\x00WAVEaudio", "voice.wav", "tr")
    assert result == {"text": "Merhaba dünya", "language": "tr"}
    assert captured["url"] == "http://127.0.0.1:8766/inference"
    assert captured["data"] == {"response_format": "json", "language": "tr"}
    assert captured["headers"] == {}


def test_whisper_cpp_converts_browser_audio_to_wav(app, monkeypatch):
    captured = {}
    wav = b"RIFF\x00\x00\x00\x00WAVEconverted"

    def run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs["input"]
        return SimpleNamespace(returncode=0, stdout=wav, stderr=b"")

    def post(url, **kwargs):
        captured["files"] = kwargs["files"]
        return FakeResponse({"text": "Salam dünya"})

    monkeypatch.setattr("app.providers.adapters.subprocess.run", run)
    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        result = WhisperCppAdapter(config()).transcribe(b"webm-opus", "voice.webm", "az")
    assert result == {"text": "Salam dünya", "language": "az"}
    assert captured["input"] == b"webm-opus"
    assert captured["files"]["file"] == ("audio.wav", wav)
    assert "ffmpeg" in captured["command"]


def test_whisper_cpp_filters_marker_only_non_speech(app, monkeypatch):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse({"text": "[MÜZİK ÇALIYO4]"}),
    )
    with app.app_context():
        result = WhisperCppAdapter(config()).transcribe(b"RIFF\x00\x00\x00\x00WAVEaudio", "voice.wav", "tr")
    assert result == {"text": "", "language": "tr"}


def test_whisper_cpp_preserves_spoken_music_sentence(app, monkeypatch):
    monkeypatch.setattr(
        "app.providers.adapters.requests.post",
        lambda *args, **kwargs: FakeResponse({"text": "Müzik çalıyor mu?"}),
    )
    with app.app_context():
        result = WhisperCppAdapter(config()).transcribe(b"RIFF\x00\x00\x00\x00WAVEaudio", "voice.wav", "tr")
    assert result == {"text": "Müzik çalıyor mu?", "language": "tr"}


def test_whisper_cpp_filters_three_identical_hallucinated_lines(app, monkeypatch):
    repeated = "Bu videonun bir şey var.\nBu videonun bir şey var.\nBu videonun bir şey var."
    monkeypatch.setattr("app.providers.adapters.requests.post", lambda *args, **kwargs: FakeResponse({"text": repeated}))
    with app.app_context():
        result = WhisperCppAdapter(config()).transcribe(b"RIFF\x00\x00\x00\x00WAVEaudio", "voice.wav", "tr")
    assert result == {"text": "", "language": "tr"}


def test_whisper_cpp_is_loopback_only(app):
    invalid = config()
    invalid.base_url = "https://remote.example/inference"
    with app.app_context():
        try:
            WhisperCppAdapter(invalid).base
        except ProviderFailure as error:
            assert error.code == "provider_invalid"
        else:
            raise AssertionError("remote whisper.cpp endpoint should be rejected")

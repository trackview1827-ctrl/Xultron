import json

from app.providers.adapters import AnthropicAdapter
from app.providers.base import ProviderConfig
from tests.conftest import post_json


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.headers = {"Content-Type": "application/json"}
        self.encoding = "utf-8"
        self.content = json.dumps(payload).encode()
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield self.content

    def close(self):
        self.closed = True


def anthropic_config():
    return ProviderConfig(
        id="anthropic-test",
        name="Anthropic Claude",
        kind="ai",
        adapter="anthropic",
        base_url="https://api.anthropic.com",
        api_key="test-anthropic-key",
        model="claude-sonnet-5",
        temperature=0.2,
        max_tokens=None,
        streaming=True,
        config={},
    )


def test_anthropic_adapter_uses_native_headers_and_message_shape(app, monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse({"content": [{"type": "text", "text": "Merhaba"}, {"type": "text", "text": " Local User"}]})

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        result = AnthropicAdapter(anthropic_config()).complete([
            {"role": "system", "content": "Kısa cevap ver."},
            {"role": "user", "content": "Merhaba"},
        ])

    assert result == "Merhaba Local User"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "test-anthropic-key"
    assert "test-anthropic-key" not in captured["url"]
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["system"] == "Kısa cevap ver."
    assert captured["json"]["messages"] == [{"role": "user", "content": "Merhaba"}]
    assert captured["json"]["max_tokens"] == 4096


def test_anthropic_model_discovery(app, monkeypatch):
    payload = {"data": [{"id": "claude-sonnet-5", "display_name": "Claude Sonnet 5"}]}
    monkeypatch.setattr("app.providers.adapters.requests.get", lambda *args, **kwargs: FakeResponse(payload))
    with app.app_context():
        models = AnthropicAdapter(anthropic_config()).models()
    assert models == [{"id": "claude-sonnet-5", "label": "Claude Sonnet 5"}]


def test_anthropic_provider_is_rejected_for_voice_kinds(user_client):
    response = post_json(user_client, "/api/v1/providers", {
        "name": "Wrong Anthropic",
        "kind": "tts",
        "adapter": "anthropic",
        "baseUrl": "https://api.anthropic.com",
        "model": "claude-sonnet-5",
    })
    assert response.status_code == 422

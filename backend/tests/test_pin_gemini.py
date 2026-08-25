import json

from app.extensions import db
from app.models import User
from app.providers.adapters import GeminiAdapter
from app.providers.base import ProviderConfig
from tests.conftest import csrf, post_json


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


def gemini_config():
    return ProviderConfig(
        id="gemini-test",
        name="Gemini",
        kind="ai",
        adapter="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="test-gemini-key",
        model="gemini-2.5-flash",
        temperature=0.2,
        max_tokens=512,
        streaming=True,
        config={},
    )


def test_local_local-user_pin_requires_four_digits_and_is_hashed(client, app):
    short = post_json(client, "/api/v1/auth/login", {"identifier": "local-user", "password": "132"})
    assert short.status_code == 422
    letters = post_json(client, "/api/v1/auth/login", {"identifier": "local-user", "password": "abcd"})
    assert letters.status_code == 422
    wrong = post_json(client, "/api/v1/auth/login", {"identifier": "local-user", "password": "9999"})
    assert wrong.status_code == 401

    success = post_json(client, "/api/v1/auth/login", {"identifier": "Local User", "password": "2468"})
    assert success.status_code == 200
    assert success.get_json()["user"]["username"] == "local-user"
    with app.app_context():
        user = User.query.filter_by(username="local-user").one()
        assert user.password_hash != "2468"
        assert user.check_password("2468")
        assert user.settings.to_public()["locale"] == "tr"


def test_login_has_a_dedicated_brute_force_limit(client, app):
    token = csrf(client)
    previous = app.config["AUTH_RATE_LIMIT_PER_MINUTE"]
    app.config["AUTH_RATE_LIMIT_PER_MINUTE"] = 2
    request = {
        "json": {"identifier": "local-user", "password": "9999"},
        "headers": {"X-CSRF-Token": token},
        "environ_overrides": {"REMOTE_ADDR": "203.0.113.231"},
    }
    try:
        assert client.post("/api/v1/auth/login", **request).status_code == 401
        assert client.post("/api/v1/auth/login", **request).status_code == 401
        assert client.post("/api/v1/auth/login", **request).status_code == 429
    finally:
        app.config["AUTH_RATE_LIMIT_PER_MINUTE"] = previous


def test_gemini_adapter_uses_header_auth_and_translates_messages(app, monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse({"candidates": [{"content": {"parts": [{"text": "Merhaba"}, {"text": " Local User"}]}}]})

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        result = GeminiAdapter(gemini_config()).complete([
            {"role": "system", "content": "Türkçe yanıt ver."},
            {"role": "user", "content": "Merhaba"},
        ])

    assert result == "Merhaba Local User"
    assert captured["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert "test-gemini-key" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert captured["json"]["systemInstruction"]["parts"][0]["text"] == "Türkçe yanıt ver."
    assert captured["json"]["contents"][0] == {"role": "user", "parts": [{"text": "Merhaba"}]}


def test_gemini_uses_large_complete_answer_default(app, monkeypatch):
    captured = {}
    config = gemini_config()
    config.max_tokens = None

    def post(url, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"candidates": [{"content": {"parts": [{"text": "Tam cevap"}]}}]})

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    with app.app_context():
        assert GeminiAdapter(config).complete([{"role": "user", "content": "Açıkla"}]) == "Tam cevap"

    assert captured["json"]["generationConfig"]["maxOutputTokens"] == 4096


def test_gemini_model_discovery_filters_non_generation_models(app, monkeypatch):
    payload = {
        "models": [
            {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-001", "displayName": "Embedding", "supportedGenerationMethods": ["embedContent"]},
        ]
    }
    monkeypatch.setattr("app.providers.adapters.requests.get", lambda *args, **kwargs: FakeResponse(payload))
    with app.app_context():
        models = GeminiAdapter(gemini_config()).models()
    assert models == [{"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"}]


def test_gemini_provider_is_rejected_for_voice_kinds(user_client):
    response = post_json(user_client, "/api/v1/providers", {
        "name": "Wrong Gemini",
        "kind": "stt",
        "adapter": "gemini",
        "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.5-flash",
    })
    assert response.status_code == 422


def test_only_implemented_interface_locales_are_accepted(user_client):
    response = user_client.patch(
        "/api/v1/settings",
        json={"locale": "fr"},
        headers={"X-CSRF-Token": csrf(user_client)},
    )
    assert response.status_code == 422

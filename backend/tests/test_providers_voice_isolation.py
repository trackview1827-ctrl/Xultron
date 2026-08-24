import io
from app.models import ProviderCredential
from app.security.crypto import decrypt_secret
from tests.conftest import delete_json, guest, patch_json, post_json, register


def create_mock_provider(client, kind="ai", **extra):
    body = {"name": f"Mock {kind}", "kind": kind, "adapter": "mock", "apiKey": "sk-secret1234567890abcd", "model": "mock-1", "enabled": True, "isDefault": True, "config": {"reply": "safe mock reply", **extra.pop("config", {})}}
    body.update(extra)
    rv = post_json(client, "/api/v1/providers", body)
    assert rv.status_code == 201, rv.get_data(as_text=True)
    return rv.get_json()["provider"]


def test_provider_secret_non_exposure_encryption_and_mock_chat(user_client, app):
    provider = create_mock_provider(user_client)
    assert "apiKey" not in provider
    assert provider["credential"]["configured"] is True
    assert "secret123" not in str(provider)
    with app.app_context():
        cred = ProviderCredential.query.first()
        raw = cred.encrypted_api_key
        assert b"sk-secret" not in raw
        assert decrypt_secret(raw).startswith("sk-secret")
    models = post_json(user_client, f"/api/v1/providers/{provider['id']}/models", {})
    assert models.get_json()["models"][0]["id"] == "mock-1"
    chat = post_json(user_client, "/api/v1/chat/messages", {"message": "hi", "requestId": "mock-chat"})
    assert chat.get_json()["messages"][-1]["content"] == "safe mock reply"


def test_invalid_provider_failure(user_client):
    provider = post_json(user_client, "/api/v1/providers", {"name": "Bad", "kind": "ai", "adapter": "openai_compatible", "enabled": True}).get_json()["provider"]
    rv = post_json(user_client, f"/api/v1/providers/{provider['id']}/test", {})
    assert rv.status_code == 422
    assert "error" in rv.get_json()
    assert "sk-" not in rv.get_data(as_text=True)


def test_voice_mock_and_audio_limits(user_client, app):
    stt = create_mock_provider(user_client, "stt", config={"transcript": "hello voice"})
    tts = create_mock_provider(user_client, "tts")
    token = user_client.get("/api/v1/auth/session").get_json()["csrfToken"]
    rv = user_client.post("/api/v1/voice/transcribe", data={"audio": (io.BytesIO(b"abc"), "a.webm"), "providerId": stt["id"]}, content_type="multipart/form-data", headers={"X-CSRF-Token": token})
    assert rv.status_code == 200
    assert rv.get_json()["text"] == "hello voice"
    audio = post_json(user_client, "/api/v1/voice/synthesize", {"text": "say hi", "providerId": tts["id"]})
    assert audio.status_code == 200
    assert audio.data.startswith(b"MOCK-AUDIO")
    old = app.config["MAX_AUDIO_BYTES"]
    app.config["MAX_AUDIO_BYTES"] = 2
    try:
        token = user_client.get("/api/v1/auth/session").get_json()["csrfToken"]
        too_big = user_client.post("/api/v1/voice/transcribe", data={"audio": (io.BytesIO(b"abc"), "big.webm"), "providerId": stt["id"]}, content_type="multipart/form-data", headers={"X-CSRF-Token": token})
        assert too_big.status_code == 413
    finally:
        app.config["MAX_AUDIO_BYTES"] = old


def test_user_and_guest_idor_isolation(app):
    a = app.test_client(); b = app.test_client(); g = app.test_client()
    register(a, "auser", "a@example.com", "password123")
    register(b, "buser", "b@example.com", "password123")
    guest(g)
    conv = post_json(a, "/api/v1/chat/conversations", {"title": "A"}).get_json()["conversation"]
    mem = post_json(a, "/api/v1/memory", {"title": "A mem", "content": "secret", "category": "important"}).get_json()["memory"]
    provider = create_mock_provider(a)
    patch_json(a, "/api/v1/settings", {"lowDataMode": True})

    for client in (b, g):
        assert client.get(f"/api/v1/chat/conversations/{conv['id']}").status_code == 403
        assert client.get(f"/api/v1/chat/conversations/{conv['id']}/messages").status_code == 403
        assert client.get(f"/api/v1/memory/{mem['id']}").status_code == 403
        assert client.get(f"/api/v1/providers/{provider['id']}").status_code == 403
        assert delete_json(client, f"/api/v1/providers/{provider['id']}").status_code == 403
        assert client.get("/api/v1/providers").get_json()["providers"] == []
    assert b.get("/api/v1/settings").get_json()["settings"]["lowDataMode"] is False

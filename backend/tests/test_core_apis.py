from tests.conftest import delete_json, patch_json, post_json, register


def test_health_settings_memory_devices(user_client):
    assert user_client.get("/api/v1/system/health").get_json()["status"] == "online"
    settings = user_client.get("/api/v1/settings")
    assert settings.status_code == 200
    assert settings.get_json()["settings"]["analytics"] is False
    patched = patch_json(user_client, "/api/v1/settings", {"lowDataMode": True, "analytics": True})
    assert patched.get_json()["settings"]["lowDataMode"] is True
    assert patched.get_json()["settings"]["analytics"] is True
    mem = post_json(user_client, "/api/v1/memory", {"title": "Food", "content": "Likes pears", "category": "preferences"})
    assert mem.status_code == 201
    mem_id = mem.get_json()["memory"]["id"]
    assert user_client.get("/api/v1/memory?query=pears").get_json()["memories"][0]["id"] == mem_id
    patched_mem = patch_json(user_client, f"/api/v1/memory/{mem_id}", {"content": "Likes apples"})
    assert "apples" in patched_mem.get_json()["memory"]["content"]
    assert user_client.get("/api/v1/devices").get_json()["devices"] == []
    clear = delete_json(user_client, "/api/v1/memory", {"confirm": "CLEAR"})
    assert clear.status_code == 200
    assert user_client.get("/api/v1/memory").get_json()["memories"] == []


def test_conversations_messages_no_provider_and_idempotency(user_client):
    c = post_json(user_client, "/api/v1/chat/conversations", {"title": "Test"})
    assert c.status_code == 201
    conv_id = c.get_json()["conversation"]["id"]
    m1 = post_json(user_client, "/api/v1/chat/messages", {"conversationId": conv_id, "message": "Hello 🌌", "requestId": "idem-1"})
    assert m1.status_code == 201
    m2 = post_json(user_client, "/api/v1/chat/messages", {"conversationId": conv_id, "message": "Hello 🌌", "requestId": "idem-1"})
    assert m2.get_json() == m1.get_json()
    conflict = post_json(user_client, "/api/v1/chat/messages", {"conversationId": conv_id, "message": "Different", "requestId": "idem-1"})
    assert conflict.status_code == 409
    messages = user_client.get(f"/api/v1/chat/conversations/{conv_id}/messages").get_json()["messages"]
    assert len(messages) == 2
    assert "No AI provider" in messages[-1]["content"]
    stream = post_json(user_client, "/api/v1/chat/stream", {"message": "stream", "requestId": "stream-1"})
    assert stream.status_code == 200
    assert b"event: done" in stream.data


def test_validation_size_and_rate_limit(user_client, app):
    empty = post_json(user_client, "/api/v1/chat/messages", {"message": "", "requestId": "e"})
    assert empty.status_code == 422
    huge = post_json(user_client, "/api/v1/chat/messages", {"message": "x" * 9000, "requestId": "huge"})
    assert huge.status_code == 422
    too_large = user_client.post("/api/v1/chat/messages", data="x" * (app.config["MAX_CONTENT_LENGTH"] + 100), content_type="application/json", headers={"X-CSRF-Token": user_client.get('/api/v1/auth/session').get_json()['csrfToken']})
    assert too_large.status_code == 413
    old = app.config["RATE_LIMIT_PER_MINUTE"]
    app.config["RATE_LIMIT_PER_MINUTE"] = 2
    try:
        assert user_client.get("/api/v1/devices").status_code == 200
        assert user_client.get("/api/v1/devices").status_code == 200
        assert user_client.get("/api/v1/devices").status_code == 429
    finally:
        app.config["RATE_LIMIT_PER_MINUTE"] = old
from app.services.providers import route_provider


def test_provider_routing_honors_declared_capabilities(user_client, app):
    first = post_json(user_client, "/api/v1/providers", {"name": "Text", "kind": "ai", "adapter": "mock", "config": {"capabilities": ["text"]}})
    second = post_json(user_client, "/api/v1/providers", {"name": "Vision", "kind": "ai", "adapter": "mock", "config": {"capabilities": ["text", "vision"]}})
    assert first.status_code == 201 and second.status_code == 201
    with app.app_context():
        user_id = user_client.get("/api/v1/auth/session").get_json()["user"]["id"]
        selected = route_provider(user_id, required_capabilities=("vision",))
        assert selected.id == second.get_json()["provider"]["id"]

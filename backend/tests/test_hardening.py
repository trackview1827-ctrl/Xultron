import io
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.serving import make_server

from app import create_app
from app.config import Config, TestingConfig
from app.extensions import db
from app.models import Conversation, IdempotencyKey, Message, Session, User
from tests.conftest import csrf, post_json, register
from tests.test_providers_voice_isolation import create_mock_provider


SENTINEL = "sk-SENTINELSECRET123456"


def test_auth_normalization_password_rotation_and_guest_rules(client, app):
    created = register(client, "  MiXeD.User  ", "UPPER@example.com", "  password123  ")
    assert created["username"] == "mixed.user"
    assert created["email"] == "upper@example.com"
    with app.app_context():
        old_session = Session.query.first()
        old_sid = old_session.id
        assert User.query.filter_by(username="mixed.user").first().check_password("  password123  ")
        assert not User.query.filter_by(username="mixed.user").first().check_password("password123")

    second_register = post_json(client, "/api/v1/auth/register", {"username": "other", "email": "other@example.com", "password": "password1234"})
    assert second_register.status_code == 409
    guest_while_authenticated = post_json(client, "/api/v1/auth/guest", {})
    assert guest_while_authenticated.status_code == 409
    out = post_json(client, "/api/v1/auth/logout", {})
    assert out.status_code == 200
    with app.app_context():
        assert db.session.get(Session, old_sid).revoked_at is not None
    assert client.get("/api/v1/settings").status_code == 401

    token = csrf(client)
    login = client.post("/api/v1/auth/login", json={"identifier": "MIXED.USER", "password": "  password123  "}, headers={"X-CSRF-Token": token})
    assert login.status_code == 200
    assert login.get_json()["csrfToken"] != token
    out2 = post_json(client, "/api/v1/auth/logout", {})
    logout_token = out2.get_json()["csrfToken"]
    guest_rv = client.post("/api/v1/auth/guest", json={}, headers={"X-CSRF-Token": logout_token})
    assert guest_rv.status_code == 201
    guest_token = guest_rv.get_json()["csrfToken"]
    upgrade = client.post("/api/v1/auth/register", json={"username": "after.logout", "email": "after@example.com", "password": "password1234"}, headers={"X-CSRF-Token": guest_token})
    assert upgrade.status_code == 201


def test_provider_config_secret_bypass_and_api_key_type_rejected(user_client):
    base = {"name": "Bad", "kind": "ai", "adapter": "mock", "model": "m", "enabled": True, "isDefault": True}
    for config in [
        {"headers": {"X-Foo": "SENTINEL"}},
        {"reply": ["ok", {"token": "SENTINEL"}]},
        {"reply": [[[[[{"ok": True}]]]]]},
    ]:
        rv = post_json(user_client, "/api/v1/providers", {**base, "config": config})
        assert rv.status_code == 422
        assert "SENTINEL" not in rv.get_data(as_text=True)
    typed_reply = post_json(user_client, "/api/v1/providers", {**base, "name": "Typed reply", "config": {"reply": SENTINEL}})
    assert typed_reply.status_code == 201
    assert typed_reply.get_json()["provider"]["config"]["reply"] == SENTINEL
    rv = post_json(user_client, "/api/v1/providers", {**base, "apiKey": {"value": SENTINEL}, "config": {"reply": "ok"}})
    assert rv.status_code == 422
    good_tts = post_json(user_client, "/api/v1/providers", {"name": "TTS", "kind": "tts", "adapter": "mock", "model": "m", "enabled": True, "isDefault": True, "config": {"speed": 1.25, "voice": "alloy"}})
    assert good_tts.status_code == 201
    bad_speed = post_json(user_client, "/api/v1/providers", {"name": "TTS2", "kind": "tts", "adapter": "mock", "model": "m", "enabled": True, "isDefault": True, "config": {"speed": 9}})
    assert bad_speed.status_code == 422


def test_provider_url_and_settings_validation(user_client):
    invalid = post_json(user_client, "/api/v1/providers", {"name": "Bad URL", "kind": "ai", "adapter": "openai_compatible", "baseUrl": "https://user:pass@example.com/v1"})
    assert invalid.status_code == 422
    bad_settings = user_client.patch("/api/v1/settings", json={"theme": "neon", "lowDataMode": "yes"}, headers={"X-CSRF-Token": csrf(user_client)})
    assert bad_settings.status_code == 422
    good_settings = user_client.patch("/api/v1/settings", json={"theme": "darker", "accent": "violet", "textScale": "large", "locale": "tr", "sttLanguage": "tr"}, headers={"X-CSRF-Token": csrf(user_client)})
    assert good_settings.status_code == 200
    assert good_settings.get_json()["settings"]["theme"] == "darker"
    assert good_settings.get_json()["settings"]["locale"] == "tr"
    assert good_settings.get_json()["settings"]["sttLanguage"] == "tr"
    az_settings = user_client.patch("/api/v1/settings", json={"sttLanguage": "az"}, headers={"X-CSRF-Token": csrf(user_client)})
    assert az_settings.status_code == 200
    assert az_settings.get_json()["settings"]["sttLanguage"] == "az"


def test_safe_log_validation(client, app, caplog):
    @app.get("/boom-secret-test")
    def boom_secret_test():
        raise RuntimeError(f"boom {SENTINEL}")
    caplog.set_level(logging.ERROR)
    rv = client.get("/boom-secret-test")
    assert rv.status_code == 500
    assert SENTINEL not in caplog.text
    assert "Traceback" not in caplog.text


def test_provider_malformed_responses_are_safe(user_client, monkeypatch):
    provider = post_json(user_client, "/api/v1/providers", {"name": "HTTP", "kind": "ai", "adapter": "openai_compatible", "baseUrl": "https://provider.example/v1", "apiKey": SENTINEL, "model": "m", "enabled": True, "isDefault": True, "config": {}}).get_json()["provider"]

    class BadResponse:
        status_code = 200
        content = b""
        headers = {"Content-Type": "text/plain"}
        def json(self):
            return {"choices": [{"message": {"content": {"not": "text"}}}]}

    monkeypatch.setattr("app.providers.adapters.requests.post", lambda *args, **kwargs: BadResponse())
    rv = post_json(user_client, "/api/v1/chat/messages", {"message": "hello", "requestId": "bad-provider"})
    assert rv.status_code == 502
    body = rv.get_data(as_text=True)
    assert "malformed" in body
    assert SENTINEL not in body


def test_provider_redirect_and_response_size_are_blocked(user_client, monkeypatch, app):
    post_json(user_client, "/api/v1/providers", {"name": "HTTP", "kind": "ai", "adapter": "openai_compatible", "baseUrl": "https://provider.example/v1", "model": "m", "enabled": True, "isDefault": True, "config": {}})

    class RedirectResponse:
        status_code = 302
        content = b""
        headers = {"Location": "https://elsewhere.example"}
        def json(self):
            return {}

    monkeypatch.setattr("app.providers.adapters.requests.post", lambda *args, **kwargs: RedirectResponse())
    redirect = post_json(user_client, "/api/v1/chat/messages", {"message": "hello", "requestId": "redirect-provider"})
    assert redirect.status_code == 502
    assert "redirect" in redirect.get_data(as_text=True)

    class LargeResponse:
        status_code = 200
        content = b"x" * 20
        headers = {"Content-Length": "20"}
        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    app.config["MAX_PROVIDER_RESPONSE_BYTES"] = 10
    monkeypatch.setattr("app.providers.adapters.requests.post", lambda *args, **kwargs: LargeResponse())
    too_large = post_json(user_client, "/api/v1/chat/messages", {"message": "hello", "requestId": "large-provider"})
    assert too_large.status_code == 502
    assert "too large" in too_large.get_data(as_text=True)

    streamed = {"closed": False, "requested": False}

    class StreamingLargeResponse:
        status_code = 200
        headers = {}
        encoding = "utf-8"

        def iter_content(self, chunk_size):
            yield b"123456"
            yield b"789012"

        def close(self):
            streamed["closed"] = True

    def streaming_response(*args, **kwargs):
        assert kwargs["stream"] is True
        streamed["requested"] = True
        return StreamingLargeResponse()

    monkeypatch.setattr("app.providers.adapters.requests.post", streaming_response)
    progressively_too_large = post_json(user_client, "/api/v1/chat/messages", {"message": "hello", "requestId": "streaming-large-provider"})
    assert progressively_too_large.status_code == 502
    assert "too large" in progressively_too_large.get_data(as_text=True)
    assert streamed == {"closed": True, "requested": True}


def test_conversation_history_false_does_not_persist_message_content(user_client, app):
    create_mock_provider(user_client, config={"reply": "assistant private sentinel"})
    settings = user_client.patch("/api/v1/settings", json={"conversationHistory": False}, headers={"X-CSRF-Token": csrf(user_client)})
    assert settings.status_code == 200
    rv = post_json(user_client, "/api/v1/chat/messages", {"message": "user private sentinel", "requestId": "private-1"})
    assert rv.status_code == 201
    assert rv.get_json()["conversation"]["title"] == "Private conversation"
    repeat = post_json(user_client, "/api/v1/chat/messages", {"message": "user private sentinel", "requestId": "private-1"})
    assert repeat.get_json() == rv.get_json()
    conflict = post_json(user_client, "/api/v1/chat/messages", {"message": "changed private sentinel", "requestId": "private-1"})
    assert conflict.status_code == 409
    with app.app_context():
        assert Message.query.count() == 0
        assert IdempotencyKey.query.count() == 0
        stored = " ".join(c.title for c in Conversation.query.all())
        assert "private sentinel" not in stored


def test_ephemeral_idempotency_cache_is_bounded():
    from app.services import chat

    with chat._EPHEMERAL_IDEM_LOCK:
        chat._EPHEMERAL_IDEM.clear()
    try:
        for index in range(chat.EPHEMERAL_IDEM_MAX_ENTRIES + 1):
            chat._ephemeral_put("user", f"request-{index}", f"fingerprint-{index}", {"index": index})
        with chat._EPHEMERAL_IDEM_LOCK:
            assert len(chat._EPHEMERAL_IDEM) == chat.EPHEMERAL_IDEM_MAX_ENTRIES
            assert ("user", "request-0") not in chat._EPHEMERAL_IDEM
    finally:
        with chat._EPHEMERAL_IDEM_LOCK:
            chat._EPHEMERAL_IDEM.clear()


def test_current_message_survives_large_memory_context(user_client, monkeypatch):
    captured = {}

    def capture_complete(self, messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr("app.providers.adapters.MockAdapter.complete", capture_complete)
    create_mock_provider(user_client)
    big = "memory filler " * 1000
    for i in range(20):
        post_json(user_client, "/api/v1/memory", {"title": f"m{i}", "content": big, "category": "personal"})
    prompt = "CURRENT PROMPT MUST ARRIVE " + ("z" * 2000)
    rv = post_json(user_client, "/api/v1/chat/messages", {"message": prompt, "requestId": "budget-current"})
    assert rv.status_code == 201
    assert captured["messages"][-1] == {"role": "user", "content": prompt}


def test_message_refreshes_conversation_order_timestamp(user_client, app):
    create_mock_provider(user_client)
    conversation = post_json(user_client, "/api/v1/chat/conversations", {"title": "Old thread"}).get_json()["conversation"]
    old = datetime(2000, 1, 1)
    with app.app_context():
        row = db.session.get(Conversation, conversation["id"])
        row.updated_at = old
        db.session.commit()

    sent = post_json(user_client, "/api/v1/chat/messages", {"conversationId": conversation["id"], "message": "refresh", "requestId": "refresh-thread"})
    assert sent.status_code == 201
    with app.app_context():
        assert db.session.get(Conversation, conversation["id"]).updated_at > old


def test_stream_endpoint_over_live_http(user_client, app, monkeypatch):
    # Copy authenticated cookies from the Flask client into a real HTTP request.
    token = csrf(user_client)
    cookie_header = "; ".join(f"{cookie.key}={cookie.value}" for cookie in user_client._cookies.values())
    app.config["SERVER_NAME"] = None
    server = make_server("localhost", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://localhost:{server.server_port}/api/v1/chat/stream"
        response = requests.post(url, json={"message": "live", "requestId": "live-stream-1"}, headers={"X-CSRF-Token": token, "Cookie": cookie_header}, timeout=5)
        assert response.status_code == 200
        assert "event: done" in response.text
        assert response.headers["Cache-Control"] == "no-cache, no-transform"
        assert response.headers["X-Accel-Buffering"] == "no"

        def fail_safely(*args, **kwargs):
            raise RuntimeError(SENTINEL)

        monkeypatch.setattr("app.api.routes.handle_message", fail_safely)
        failed = requests.post(url, json={"message": "fail", "requestId": "live-stream-2"}, headers={"X-CSRF-Token": token, "Cookie": cookie_header}, timeout=5)
        assert failed.status_code == 200
        assert "event: error" in failed.text
        assert '"code": "internal_error"' in failed.text
        assert "event: done" in failed.text
        assert SENTINEL not in failed.text
        assert "/data/" not in failed.text
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_static_spa_headers_and_production_fail_closed(tmp_path):
    dist = tmp_path / "frontend-dist"
    assets = dist / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<div id='root'>Xultron</div>")
    (assets / "app.js").write_text("console.log('x')")
    (dist / "sw.js").write_text("self.addEventListener('install', () => {})")

    class StaticTestingConfig(TestingConfig):
        FRONTEND_DIST_DIR = str(dist)

    app = create_app(StaticTestingConfig)
    client = app.test_client()
    index = client.get("/settings")
    assert index.status_code == 200
    assert b"Xultron" in index.data
    assert index.headers["Cache-Control"].startswith("no-cache")
    assert index.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in index.headers["Content-Security-Policy"]
    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "immutable" in asset.headers["Cache-Control"]
    service_worker = client.get("/sw.js")
    assert service_worker.status_code == 200
    assert service_worker.headers["Cache-Control"].startswith("no-cache")
    api_missing = client.get("/api/no-such-route")
    assert api_missing.status_code == 404
    assert api_missing.is_json
    assert b"Xultron" not in api_missing.data

    class BadProduction(Config):
        XULTRON_ENV = "production"
        SECRET_KEY = None
        ENCRYPTION_KEY = None

    with pytest.raises(RuntimeError):
        create_app(BadProduction)


def _flask_db_upgrade(db_path: Path, target: str | None = None):
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "SECRET_KEY": "migration-test-secret",
        "ENCRYPTION_KEY": "dQwqt9c0YlfLH2jBZ3YV0LzhCoVqBCybN7Ko65aoFZ4=",
        "XULTRON_ENV": "development",
    }
    cmd = [sys.executable, "-m", "flask", "--app", "run", "db", "upgrade"]
    if target:
        cmd.append(target)
    result = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout


def test_real_flask_db_upgrade_empty_and_existing_0001(tmp_path):
    empty_db = tmp_path / "empty.sqlite3"
    _flask_db_upgrade(empty_db)
    engine = create_engine(f"sqlite:///{empty_db}")
    inspector = inspect(engine)
    assert "request_fingerprint" in {col["name"] for col in inspector.get_columns("idempotency_keys")}
    assert "device_commands" in inspector.get_table_names()
    assert "device_events" in inspector.get_table_names()

    old_db = tmp_path / "old.sqlite3"
    _flask_db_upgrade(old_db, "0001_initial")
    old_inspector = inspect(create_engine(f"sqlite:///{old_db}"))
    assert "request_fingerprint" not in {col["name"] for col in old_inspector.get_columns("idempotency_keys")}
    _flask_db_upgrade(old_db)
    upgraded = inspect(create_engine(f"sqlite:///{old_db}"))
    assert "request_fingerprint" in {col["name"] for col in upgraded.get_columns("idempotency_keys")}
    assert "device_commands" in upgraded.get_table_names()
    assert "device_events" in upgraded.get_table_names()


def test_request_id_sqlite_pragmas_last_n_and_voice_form_validation(user_client, app):
    bad_request_id = user_client.get("/api/v1/settings", headers={"X-Request-ID": "bad request id with spaces"})
    assert bad_request_id.status_code == 422
    assert app.config["MAX_CONTENT_LENGTH"] > app.config["MAX_AUDIO_BYTES"]
    with app.app_context():
        assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert db.session.execute(text("PRAGMA busy_timeout")).scalar() >= 5000
        db.session.add(Message(user_id="missing", conversation_id="missing", role="user", content="x"))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        else:
            raise AssertionError("SQLite foreign keys were not enforced")

    conv = post_json(user_client, "/api/v1/chat/conversations", {"title": "Last N"}).get_json()["conversation"]
    for i in range(3):
        post_json(user_client, "/api/v1/chat/messages", {"conversationId": conv["id"], "message": f"msg-{i}", "requestId": f"last-n-{i}"})
    latest = user_client.get(f"/api/v1/chat/conversations/{conv['id']}/messages?limit=2")
    contents = [m["content"] for m in latest.get_json()["messages"]]
    assert contents == ["msg-2", "No AI provider is configured yet. Add a provider in Settings to enable model-backed responses."]
    token = csrf(user_client)
    voice = user_client.post("/api/v1/voice/transcribe", data={"audio": (io.BytesIO(b"abc"), "a.webm"), "providerId": "x" * 41}, content_type="multipart/form-data", headers={"X-CSRF-Token": token})
    assert voice.status_code == 422


def test_voice_upload_filename_is_sanitized(user_client, monkeypatch):
    provider = create_mock_provider(user_client, kind="stt", config={"transcript": "safe"})
    captured = {}

    def transcribe(self, audio, filename, language):
        captured["filename"] = filename
        return {"text": "safe", "language": language}

    monkeypatch.setattr("app.providers.adapters.MockAdapter.transcribe", transcribe)
    response = user_client.post(
        "/api/v1/voice/transcribe",
        data={"audio": (io.BytesIO(b"abc"), "../../private key.webm"), "providerId": provider["id"]},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf(user_client)},
    )
    assert response.status_code == 200
    assert captured["filename"] == "private_key.webm"

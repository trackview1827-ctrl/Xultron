from datetime import timedelta

from app.extensions import db
from app.models import Session, User, utcnow
from tests.conftest import csrf, delete_json, guest, post_json, register


def test_session_csrf_and_empty_auth(client):
    rv = client.get("/api/v1/auth/session")
    assert rv.status_code == 200
    assert rv.get_json()["user"] is None
    assert rv.get_json()["csrfToken"]
    missing = client.post("/api/v1/auth/login", json={"identifier": "", "password": ""})
    assert missing.status_code == 403
    empty = post_json(client, "/api/v1/auth/login", {"identifier": "", "password": ""})
    assert empty.status_code == 401


def test_wrong_password_and_login_logout_invalidation(client):
    register(client, "alice", "alice@example.com", "password123")
    bad = post_json(client, "/api/v1/auth/login", {"identifier": "alice", "password": "wrongpass"})
    assert bad.status_code == 401
    out = post_json(client, "/api/v1/auth/logout", {})
    assert out.status_code == 200
    assert client.get("/api/v1/settings").status_code == 401
    with client.session_transaction() as sess:
        assert "sid" not in sess


def test_guest_upgrade_preserves_own_data(client):
    user = guest(client)
    msg = post_json(client, "/api/v1/chat/messages", {"message": "hello", "requestId": "r1"})
    assert msg.status_code == 201
    conv_id = msg.get_json()["conversation"]["id"]
    upgraded = post_json(client, "/api/v1/auth/register", {"username": "upgraded", "email": "up@example.com", "password": "password123"})
    assert upgraded.status_code == 201
    assert upgraded.get_json()["user"]["id"] == user["id"]
    assert upgraded.get_json()["user"]["isGuest"] is False
    assert client.get(f"/api/v1/chat/conversations/{conv_id}").status_code == 200


def test_expired_session_is_invalidated(client, app):
    register(client, "bob", "bob@example.com", "password123")
    with app.app_context():
        rec = Session.query.first()
        rec.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert client.get("/api/v1/settings").status_code == 401


def test_same_origin_and_csrf(client):
    token = csrf(client)
    bad_origin = client.post("/api/v1/auth/register", json={"username": "x", "email": "x@example.com", "password": "password123"}, headers={"X-CSRF-Token": token, "Origin": "https://evil.example"})
    assert bad_origin.status_code == 403
    bad_csrf = client.post("/api/v1/auth/register", json={"username": "x", "email": "x@example.com", "password": "password123"}, headers={"X-CSRF-Token": "bad"})
    assert bad_csrf.status_code == 403


def test_revoke_other_owned_session(client, app):
    register(client, "owner", "owner@example.com", "password123")
    sessions = client.get("/api/v1/auth/sessions").get_json()["sessions"]
    assert len(sessions) == 1
    rv = delete_json(client, f"/api/v1/auth/sessions/{sessions[0]['id']}")
    assert rv.status_code == 200
    assert client.get("/api/v1/auth/sessions").status_code == 401

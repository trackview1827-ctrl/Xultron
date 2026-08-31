import hashlib
from datetime import timedelta

from app.extensions import db
from app.models import (
    MobileAccessToken,
    MobileAuthEvent,
    MobileAuthSession,
    MobileRefreshToken,
    utcnow,
)
from tests.conftest import csrf, post_json, register


def device(installation_id, name="Pixel Test"):
    return {
        "installationId": installation_id,
        "name": name,
        "type": "android",
        "appVersion": "1.0.0-test",
        "metadata": {"sdk": 35},
    }


def enroll(client, username, installation_id):
    response = client.post(
        "/api/v1/device-auth/enroll",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
            "device": device(installation_id),
        },
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_mobile_enroll_tokens_are_hashed_and_bearer_works_without_csrf(client, app):
    issued = enroll(client, "mobile_alice", "install-alice-0001")

    assert issued["tokenType"] == "Bearer"
    assert issued["accessToken"].startswith("mat_")
    assert issued["refreshToken"].startswith("mrt_")
    assert issued["expiresIn"] <= 900
    settings = client.get("/api/v1/settings", headers=bearer(issued["accessToken"]))
    assert settings.status_code == 200

    update = client.patch(
        "/api/v1/settings",
        json={"lowDataMode": True},
        headers=bearer(issued["accessToken"]),
    )
    assert update.status_code == 200

    with app.app_context():
        access = MobileAccessToken.query.one()
        refresh = MobileRefreshToken.query.one()
        assert access.token_hash == hashlib.sha256(issued["accessToken"].encode()).hexdigest()
        assert refresh.token_hash == hashlib.sha256(issued["refreshToken"].encode()).hexdigest()
        assert issued["accessToken"] not in access.token_hash
        assert issued["refreshToken"] not in refresh.token_hash
        assert MobileAuthEvent.query.filter_by(event_type="enrollment_succeeded").count() == 1


def test_refresh_rotates_once_and_reuse_revokes_entire_family(client, app):
    first = enroll(client, "rotate_user", "install-rotate-001")
    rotated_response = client.post(
        "/api/v1/device-auth/refresh",
        json={"refreshToken": first["refreshToken"]},
    )
    assert rotated_response.status_code == 200
    rotated = rotated_response.get_json()
    assert rotated["refreshToken"] != first["refreshToken"]
    assert rotated["accessToken"] != first["accessToken"]

    with app.app_context():
        old = MobileRefreshToken.query.filter_by(
            token_hash=hashlib.sha256(first["refreshToken"].encode()).hexdigest()
        ).one()
        new = MobileRefreshToken.query.filter_by(
            token_hash=hashlib.sha256(rotated["refreshToken"].encode()).hexdigest()
        ).one()
        assert old.consumed_at is not None
        assert new.parent_id == old.id

    replay = client.post(
        "/api/v1/device-auth/refresh",
        json={"refreshToken": first["refreshToken"]},
    )
    assert replay.status_code == 401
    assert replay.get_json()["error"]["code"] == "refresh_reuse_detected"

    assert client.get("/api/v1/settings", headers=bearer(first["accessToken"])).status_code == 401
    assert client.get("/api/v1/settings", headers=bearer(rotated["accessToken"])).status_code == 401
    latest = client.post(
        "/api/v1/device-auth/refresh",
        json={"refreshToken": rotated["refreshToken"]},
    )
    assert latest.status_code == 401
    assert latest.get_json()["error"]["code"] == "refresh_token_revoked"

    with app.app_context():
        family = MobileAuthSession.query.one()
        assert family.revoked_at is not None
        assert family.revoke_reason == "refresh_reuse"
        assert MobileAuthEvent.query.filter_by(event_type="refresh_reuse_detected").count() == 1


def test_expired_access_and_refresh_tokens_are_rejected(client, app):
    issued = enroll(client, "expired_user", "install-expired-01")
    with app.app_context():
        MobileAccessToken.query.one().expires_at = utcnow() - timedelta(seconds=1)
        MobileRefreshToken.query.one().expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()

    access = client.get("/api/v1/settings", headers=bearer(issued["accessToken"]))
    assert access.status_code == 401
    assert access.get_json()["error"]["code"] == "access_token_expired"
    refresh = client.post(
        "/api/v1/device-auth/refresh",
        json={"refreshToken": issued["refreshToken"]},
    )
    assert refresh.status_code == 401
    assert refresh.get_json()["error"]["code"] == "refresh_token_expired"


def test_logout_and_owned_revoke_invalidate_mobile_credentials(client):
    issued = enroll(client, "logout_user", "install-logout-001")
    logout = client.post(
        "/api/v1/device-auth/logout",
        json={},
        headers=bearer(issued["accessToken"]),
    )
    assert logout.status_code == 200
    assert client.get("/api/v1/settings", headers=bearer(issued["accessToken"])).status_code == 401
    assert (
        client.post(
            "/api/v1/device-auth/refresh",
            json={"refreshToken": issued["refreshToken"]},
        ).get_json()["error"]["code"]
        == "refresh_token_revoked"
    )

    second = client.post(
        "/api/v1/device-auth/login",
        json={
            "identifier": "logout_user",
            "password": "password123",
            "device": device("install-logout-001"),
        },
    ).get_json()
    revoked = client.post(
        "/api/v1/device-auth/revoke",
        json={"sessionId": second["session"]["id"]},
        headers=bearer(second["accessToken"]),
    )
    assert revoked.status_code == 200
    assert client.get("/api/v1/settings", headers=bearer(second["accessToken"])).status_code == 401


def test_device_revoke_cancels_all_device_families_and_password_can_reauthorize(client):
    first = enroll(client, "device_revoke_user", "install-device-revoke")
    second_response = client.post(
        "/api/v1/device-auth/login",
        json={
            "identifier": "device_revoke_user",
            "password": "password123",
            "device": device("install-device-revoke"),
        },
    )
    assert second_response.status_code == 200
    second = second_response.get_json()

    sessions = client.get(
        "/api/v1/device-auth/sessions", headers=bearer(second["accessToken"])
    )
    assert sessions.status_code == 200
    assert len(sessions.get_json()["sessions"]) == 2

    revoked = client.post(
        "/api/v1/device-auth/revoke",
        json={"deviceId": second["session"]["device"]["id"]},
        headers=bearer(second["accessToken"]),
    )
    assert revoked.status_code == 200
    assert client.get("/api/v1/settings", headers=bearer(first["accessToken"])).status_code == 401
    assert client.get("/api/v1/settings", headers=bearer(second["accessToken"])).status_code == 401
    assert (
        client.post(
            "/api/v1/device-auth/refresh",
            json={"refreshToken": first["refreshToken"]},
        ).status_code
        == 401
    )

    relogin = client.post(
        "/api/v1/device-auth/login",
        json={
            "identifier": "device_revoke_user",
            "password": "password123",
            "device": device("install-device-revoke"),
        },
    )
    assert relogin.status_code == 200
    assert (
        client.get(
            "/api/v1/settings",
            headers=bearer(relogin.get_json()["accessToken"]),
        ).status_code
        == 200
    )


def test_cross_user_session_device_and_resource_access_is_denied(client):
    alice = enroll(client, "cross_alice", "install-cross-alice")
    bob = enroll(client, "cross_bob", "install-cross-bob-01")

    conversation = client.post(
        "/api/v1/chat/messages",
        json={"message": "private", "requestId": "mobile-cross-1"},
        headers=bearer(alice["accessToken"]),
    )
    assert conversation.status_code == 201
    conversation_id = conversation.get_json()["conversation"]["id"]
    assert (
        client.get(
            f"/api/v1/chat/conversations/{conversation_id}",
            headers=bearer(bob["accessToken"]),
        ).status_code
        == 403
    )

    revoke_session = client.post(
        "/api/v1/device-auth/revoke",
        json={"sessionId": alice["session"]["id"]},
        headers=bearer(bob["accessToken"]),
    )
    assert revoke_session.status_code == 403
    revoke_device = client.post(
        "/api/v1/device-auth/revoke",
        json={"deviceId": alice["session"]["device"]["id"]},
        headers=bearer(bob["accessToken"]),
    )
    assert revoke_device.status_code == 403
    assert client.get("/api/v1/settings", headers=bearer(alice["accessToken"])).status_code == 200


def test_guest_upgrade_preserves_identity_and_revokes_guest_family(client):
    guest_response = client.post(
        "/api/v1/device-auth/guest",
        json={"device": device("install-guest-0001")},
    )
    assert guest_response.status_code == 201
    guest = guest_response.get_json()
    assert guest["user"]["isGuest"] is True
    assert client.get("/api/v1/settings", headers=bearer(guest["accessToken"])).status_code == 200

    upgraded_response = client.post(
        "/api/v1/device-auth/enroll",
        json={
            "username": "guest_upgraded",
            "email": "guest_upgraded@example.com",
            "password": "password123",
            "device": device("install-guest-0001", "Upgraded Pixel"),
        },
        headers=bearer(guest["accessToken"]),
    )
    assert upgraded_response.status_code == 201
    upgraded = upgraded_response.get_json()
    assert upgraded["user"]["id"] == guest["user"]["id"]
    assert upgraded["user"]["isGuest"] is False
    assert client.get("/api/v1/settings", headers=bearer(guest["accessToken"])).status_code == 401
    assert client.get("/api/v1/settings", headers=bearer(upgraded["accessToken"])).status_code == 200


def test_device_registration_is_bound_to_current_mobile_session(client):
    issued = enroll(client, "device_user", "install-device-001")
    updated = client.post(
        "/api/v1/devices/register",
        json=device("install-device-001", "Renamed Pixel"),
        headers=bearer(issued["accessToken"]),
    )
    assert updated.status_code == 200
    assert updated.get_json()["device"]["name"] == "Renamed Pixel"

    mismatch = client.post(
        "/api/v1/devices/register",
        json=device("install-device-999", "Other Device"),
        headers=bearer(issued["accessToken"]),
    )
    assert mismatch.status_code == 409
    assert mismatch.get_json()["error"]["code"] == "device_mismatch"


def test_access_token_rejects_an_explicit_wrong_device_binding(client):
    issued = enroll(client, "bound_device_user", "install-bound-device")
    response = client.get(
        "/api/v1/settings",
        headers={
            "Authorization": f"Bearer {issued['accessToken']}",
            "X-Device-ID": "dev_wrong_device",
        },
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "device_mismatch"


def test_mobile_login_does_not_replace_web_cookie_csrf_flow(client):
    register(client, "web_user", "web@example.com", "password123")
    web_csrf = csrf(client)
    before = client.get("/api/v1/auth/session").get_json()
    assert before["user"]["username"] == "web_user"

    mobile = client.post(
        "/api/v1/device-auth/login",
        json={
            "identifier": "web_user",
            "password": "password123",
            "device": device("install-web-user-01"),
        },
    )
    assert mobile.status_code == 200
    after = client.get("/api/v1/auth/session").get_json()
    assert after["user"]["username"] == "web_user"
    assert after["csrfToken"] == web_csrf

    missing_csrf = client.post("/api/v1/auth/logout", json={})
    assert missing_csrf.status_code == 403
    valid_logout = post_json(client, "/api/v1/auth/logout", {}, token=web_csrf)
    assert valid_logout.status_code == 200
    assert client.get("/api/v1/settings").status_code == 401
    assert (
        client.get(
            "/api/v1/settings",
            headers=bearer(mobile.get_json()["accessToken"]),
        ).status_code
        == 200
    )

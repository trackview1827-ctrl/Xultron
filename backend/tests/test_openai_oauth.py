import base64
import json
from urllib.parse import parse_qs, urlparse

from app.models import Provider
from conftest import delete_json, post_json


def create_codex_provider(client):
    response = post_json(client, "/api/v1/providers", {
            "name": "ChatGPT Codex",
            "kind": "ai",
            "adapter": "openai_codex_oauth",
            "baseUrl": "https://chatgpt.com/backend-api/codex",
            "model": "gpt-5-codex",
            "enabled": True,
            "isDefault": True,
            "config": {},
        })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["provider"]


def make_id_token(account_id="acct_test"):
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = {
        "https://api.openai.com/auth": {"chatgpt_account_id": account_id},
        "email": "oauth@example.com",
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{encoded}.signature"


def test_codex_oauth_start_returns_pkce_authorization_link(user_client):
    provider = create_codex_provider(user_client)
    response = post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})

    assert response.status_code == 200
    body = response.get_json()
    assert body["redirectUri"].endswith("/api/v1/providers/oauth/openai/callback")
    assert body["authorizationUrl"].startswith("https://auth.openai.com/oauth/authorize?")
    assert "code_challenge=" in body["authorizationUrl"]
    assert "state=" in body["authorizationUrl"]
    params = parse_qs(urlparse(body["authorizationUrl"]).query)
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["scope"] == ["openid profile email offline_access"]
    assert "connector" not in params["scope"][0]


def test_codex_oauth_callback_encrypts_tokens_and_redirects(app, user_client, monkeypatch):
    provider = create_codex_provider(user_client)
    start = post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})
    assert start.status_code == 200
    with user_client.session_transaction() as current_session:
        pending = dict(current_session["openai_oauth_pending"])

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "access_token": "access-secret",
                "refresh_token": "refresh-secret",
                "id_token": make_id_token(),
                "expires_in": 3600,
                "scope": "openid profile email offline_access",
            }

    monkeypatch.setattr("app.services.openai_oauth.requests.post", lambda *args, **kwargs: FakeResponse())
    response = user_client.get(
        f"/api/v1/providers/oauth/openai/callback?code=auth-code&state={pending['state']}"
    )

    assert response.status_code == 302
    assert "oauth=openai_success" in response.headers["Location"]
    with app.app_context():
        record = Provider.query.filter_by(id=provider["id"]).one()
        assert record.credential.encrypted_access_token
        assert record.credential.encrypted_refresh_token
        assert record.credential.oauth_account_id == "acct_test"
        assert record.to_public()["credential"]["authMethod"] == "codex_oauth"

    status = user_client.get(f"/api/v1/providers/{provider['id']}/oauth/status")
    assert status.get_json() == {
        "supported": True,
        "connected": True,
        "authMethod": "codex_oauth",
        "accountId": "acct_test",
        "expiresAt": status.get_json()["expiresAt"],
    }
    assert isinstance(status.get_json()["expiresAt"], int)
    disconnected = delete_json(user_client, f"/api/v1/providers/{provider['id']}/oauth")
    assert disconnected.status_code == 200
    assert disconnected.get_json() == {"ok": True}
    after = user_client.get(f"/api/v1/providers/{provider['id']}/oauth/status").get_json()
    assert after == {"supported": True, "connected": False, "authMethod": None, "accountId": None, "expiresAt": None}


def test_codex_oauth_callback_rejects_state_mismatch(user_client):
    provider = create_codex_provider(user_client)
    start = post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})
    assert start.status_code == 200

    response = user_client.get(
        "/api/v1/providers/oauth/openai/callback?code=auth-code&state=wrong-state"
    )

    assert response.status_code == 400
    assert "state doğrulaması başarısız" in response.get_data(as_text=True)


def test_codex_oauth_callback_failures_are_safe(user_client, monkeypatch):
    provider = create_codex_provider(user_client)

    missing_session = user_client.get("/api/v1/providers/oauth/openai/callback?code=x&state=y")
    assert missing_session.status_code == 400
    assert "oturumu bulunamadı" in missing_session.get_data(as_text=True)

    post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})
    cancelled = user_client.get("/api/v1/providers/oauth/openai/callback?error=access_denied")
    assert cancelled.status_code == 400
    assert "yetkilendirmesi iptal edildi" in cancelled.get_data(as_text=True)

    post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})
    with user_client.session_transaction() as current_session:
        missing_code_state = current_session["openai_oauth_pending"]["state"]
    missing_code = user_client.get(f"/api/v1/providers/oauth/openai/callback?state={missing_code_state}")
    assert missing_code.status_code == 400
    assert "callback code içermiyor" in missing_code.get_data(as_text=True)

    post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})
    with user_client.session_transaction() as current_session:
        exchange_state = current_session["openai_oauth_pending"]["state"]

    class FailedResponse:
        status_code = 500

    monkeypatch.setattr("app.services.openai_oauth.requests.post", lambda *args, **kwargs: FailedResponse())
    failed = user_client.get(f"/api/v1/providers/oauth/openai/callback?code=auth-code&state={exchange_state}")
    text = failed.get_data(as_text=True)
    assert failed.status_code == 502
    assert "token değişimi başarısız" in text
    assert "Traceback" not in text and "/data/" not in text


def test_oauth_routes_reject_unsupported_provider(user_client):
    provider = post_json(user_client, "/api/v1/providers", {
        "name": "Mock AI", "kind": "ai", "adapter": "mock", "enabled": True, "config": {"reply": "ok"}
    }).get_json()["provider"]
    start = post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})
    disconnect = delete_json(user_client, f"/api/v1/providers/{provider['id']}/oauth")
    assert start.status_code == 422
    assert start.get_json()["error"]["code"] == "oauth_not_supported"
    assert disconnect.status_code == 422
    assert disconnect.get_json()["error"]["code"] == "oauth_not_supported"

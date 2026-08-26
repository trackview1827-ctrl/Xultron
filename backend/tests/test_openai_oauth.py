import base64
import json

from app.models import Provider
from conftest import post_json


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


def test_codex_oauth_callback_rejects_state_mismatch(user_client):
    provider = create_codex_provider(user_client)
    start = post_json(user_client, f"/api/v1/providers/{provider['id']}/oauth/openai/start", {})
    assert start.status_code == 200

    response = user_client.get(
        "/api/v1/providers/oauth/openai/callback?code=auth-code&state=wrong-state"
    )

    assert response.status_code == 400
    assert "state doğrulaması başarısız" in response.get_data(as_text=True)

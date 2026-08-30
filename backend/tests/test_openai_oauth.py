import base64
import json
import requests
from urllib.parse import parse_qs, urlparse

from app.models import Provider
from app.providers.adapters import CodexOAuthAdapter
from app.providers.base import ProviderConfig
from app.services.openai_oauth import _backend_callback_uri
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
    assert body["redirectUri"].endswith("/auth/callback")
    assert body["authorizationUrl"].startswith("https://auth.openai.com/oauth/authorize?")
    assert "code_challenge=" in body["authorizationUrl"]
    assert "state=" in body["authorizationUrl"]
    params = parse_qs(urlparse(body["authorizationUrl"]).query)
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == [body["redirectUri"]]
    assert urlparse(body["redirectUri"]).hostname == "localhost"
    assert urlparse(body["redirectUri"]).port in {1455, 1457}
    assert params["code_challenge_method"] == ["S256"]
    assert params["scope"] == ["openid profile email offline_access api.connectors.read api.connectors.invoke"]
    relay = requests.get(
        body["redirectUri"].replace("localhost", "127.0.0.1") + "?code=relay-code&state=relay-state",
        allow_redirects=False,
        timeout=5,
    )
    assert relay.status_code == 302
    assert relay.headers["Location"].endswith("/api/v1/providers/oauth/openai/callback?code=relay-code&state=relay-state")
    relay_target = urlparse(relay.headers["Location"])
    assert relay_target.scheme == "http" and relay_target.hostname == "localhost"


def test_oauth_backend_callback_keeps_loopback_cookie_host(app):
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    with app.test_request_context("/", base_url="http://localhost:5000"):
        assert _backend_callback_uri() == "http://localhost:5000/api/v1/providers/oauth/openai/callback"
    with app.test_request_context("/", base_url="http://127.0.0.1:5000"):
        assert _backend_callback_uri() == "http://127.0.0.1:5000/api/v1/providers/oauth/openai/callback"


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

    exchange = {}

    def fake_post(*args, **kwargs):
        exchange.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.openai_oauth.requests.post", fake_post)
    response = user_client.get(
        f"/api/v1/providers/oauth/openai/callback?code=auth-code&state={pending['state']}"
    )

    assert response.status_code == 302
    assert "oauth=openai_success" in response.headers["Location"]
    assert exchange["data"]["redirect_uri"] == pending["redirectUri"]
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


def test_codex_adapter_uses_required_streaming_responses_protocol(app, monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def iter_lines(self):
            return iter([
                b'data: {"type":"response.created"}',
                b'data: {"type":"response.output_text.delta","delta":"O"}',
                b'data: {"type":"response.output_text.delta","delta":"K"}',
                b'data: {"type":"response.completed","response":{"status":"completed"}}',
                b'data: [DONE]',
            ])

        def close(self):
            captured["closed"] = True

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.providers.adapters.requests.post", fake_post)
    with app.app_context():
        adapter = CodexOAuthAdapter(ProviderConfig(
            id="prv_test",
            name="Codex",
            kind="ai",
            adapter="openai_codex_oauth",
            base_url="https://chatgpt.com/backend-api/codex",
            api_key=None,
            access_token="access-secret",
            account_id="acct_test",
            auth_mode="codex_oauth",
            model="gpt-5.6-sol",
            temperature=0.3,
            max_tokens=4096,
            streaming=True,
            config={},
        ))
        assert adapter.complete([{"role": "user", "content": "Reply OK"}]) == "OK"

    assert captured["json"]["stream"] is True
    assert captured["stream"] is True
    assert captured["closed"] is True

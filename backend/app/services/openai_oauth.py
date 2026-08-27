"""OpenAI Codex OAuth authorization-code flow."""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode
from urllib.parse import urlparse

import requests
from flask import current_app, redirect, request, session

from app.extensions import db
from app.models import Provider
from app.security.crypto import encrypt_secret
from app.security.errors import APIError
# Keep these aligned with the official Codex CLI authorization client. In particular,
# the connector scopes are required by the current public Codex client registration.
CODEX_SCOPES = "openid profile email offline_access api.connectors.read api.connectors.invoke"
CODEX_CALLBACK_PATH = "/auth/callback"
_RELAY_LOCK = threading.Lock()
_RELAY_SERVERS: dict[int, ThreadingHTTPServer] = {}


class _OAuthCallbackRelayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != CODEX_CALLBACK_PATH:
            self.send_error(404)
            return
        target = self.server.backend_callback_uri
        if parsed.query:
            target += ("&" if "?" in target else "?") + parsed.query
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        self.end_headers()
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *_args):
        return None


def _backend_callback_uri() -> str:
    configured = current_app.config.get("OPENAI_OAUTH_BACKEND_CALLBACK_URI") or current_app.config.get("OPENAI_OAUTH_REDIRECT_URI")
    parsed = urlparse(configured)
    request_host = urlparse(f"//{request.host}")
    # Keep the signed Flask session on the same loopback host the user opened.
    # Browsers do not send a localhost cookie to 127.0.0.1 (or vice versa).
    if (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and request.scheme == "http"
        and request_host.hostname in {"127.0.0.1", "localhost"}
    ):
        return f"http://{request_host.netloc}{parsed.path}"
    return configured


def _start_callback_relay() -> tuple[int, str]:
    backend_callback_uri = _backend_callback_uri()
    parsed_backend = urlparse(backend_callback_uri)
    if parsed_backend.scheme != "http" or parsed_backend.hostname not in {"127.0.0.1", "localhost"} or not parsed_backend.path:
        raise APIError("oauth_callback_invalid", "Codex OAuth callback must point to the local Xultron backend.", 500)

    ports = tuple(current_app.config.get("OPENAI_OAUTH_CALLBACK_PORTS", (1455, 1457)))
    with _RELAY_LOCK:
        for port in ports:
            if port in _RELAY_SERVERS:
                return port, f"http://localhost:{port}{CODEX_CALLBACK_PATH}"
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), _OAuthCallbackRelayHandler)
            except OSError:
                continue
            server.backend_callback_uri = backend_callback_uri
            _RELAY_SERVERS[port] = server

            def serve(relay=server, relay_port=port):
                try:
                    relay.serve_forever(poll_interval=0.2)
                finally:
                    with _RELAY_LOCK:
                        _RELAY_SERVERS.pop(relay_port, None)
                    relay.server_close()

            threading.Thread(target=serve, name=f"xultron-oauth-relay-{port}", daemon=True).start()
            return port, f"http://localhost:{port}{CODEX_CALLBACK_PATH}"
    raise APIError("oauth_callback_unavailable", "Codex OAuth için yerel callback portu kullanılamıyor.", 503)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _account_id(id_token: str | None) -> str | None:
    if not id_token or id_token.count(".") < 2:
        return None
    try:
        encoded = id_token.split(".")[1]
        encoded += "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded).decode())
        auth = payload.get("https://api.openai.com/auth", {})
        value = auth.get("chatgpt_account_id")
        return value[:160] if isinstance(value, str) and value else None
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
        return None


def start(provider: Provider) -> dict:
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(32)
    _port, redirect_uri = _start_callback_relay()
    session["openai_oauth_pending"] = {
        "state": state,
        "verifier": verifier,
        "providerId": provider.id,
        "userId": provider.user_id,
        "createdAt": int(time.time()),
        "redirectUri": redirect_uri,
    }
    params = {
        "response_type": "code",
        "client_id": current_app.config["OPENAI_OAUTH_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "scope": CODEX_SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "codex_cli_rs",
    }
    return {"authorizationUrl": f'{current_app.config["OPENAI_OAUTH_AUTHORIZE_URL"]}?{urlencode(params)}', "redirectUri": redirect_uri}


def _failure_page(message: str, status: int = 400):
    safe = html.escape(message[:300])
    body = f"<!doctype html><meta charset='utf-8'><title>Xultron OAuth</title><main><h1>ChatGPT bağlantısı tamamlanamadı</h1><p>{safe}</p><p>Bu sekmeyi kapatıp Xultron'a dön.</p></main>"
    return body, status, {"Content-Type": "text/html; charset=utf-8"}


def callback():
    pending = session.pop("openai_oauth_pending", None)
    if not isinstance(pending, dict) or int(pending.get("createdAt", 0)) < int(time.time()) - 600:
        return _failure_page("OAuth oturumu bulunamadı veya süresi doldu.")
    if request.args.get("error"):
        return _failure_page("ChatGPT yetkilendirmesi iptal edildi.")
    if request.args.get("state") != pending.get("state"):
        return _failure_page("OAuth state doğrulaması başarısız oldu.")
    code = request.args.get("code", "")
    if not code:
        return _failure_page("OAuth callback code içermiyor.")

    try:
        response = requests.post(
            current_app.config["OPENAI_OAUTH_TOKEN_URL"],
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "client_id": current_app.config["OPENAI_OAUTH_CLIENT_ID"],
                "code": code,
                "code_verifier": pending["verifier"],
                "redirect_uri": pending.get("redirectUri") or "",
            },
            timeout=current_app.config.get("PROVIDER_TIMEOUT_SECONDS", 45),
            allow_redirects=False,
        )
        if response.status_code >= 400:
            current_app.logger.warning("OpenAI OAuth token exchange failed status=%s", response.status_code)
            return _failure_page("ChatGPT token değişimi başarısız oldu.", 502)
        data = response.json()
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        id_token = data.get("id_token")
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            return _failure_page("ChatGPT token yanıtı eksik.", 502)
        expires_in = data.get("expires_in", 3600)
        try:
            expires_at = int(time.time() * 1000) + max(int(expires_in), 60) * 1000
        except (TypeError, ValueError):
            expires_at = None
        scopes = data.get("scope", "")
        if not isinstance(scopes, str):
            scopes = ""
        provider = db.session.get(Provider, pending.get("providerId"))
        if not provider or provider.user_id != pending.get("userId"):
            return _failure_page("Provider bulunamadı.", 404)
        if not provider.credential:
            from app.models import ProviderCredential
            provider.credential = ProviderCredential()
        credential = provider.credential
        credential.encrypted_api_key = None
        credential.masked_hint = None
        credential.encrypted_access_token = encrypt_secret(access_token)
        credential.encrypted_refresh_token = encrypt_secret(refresh_token)
        credential.encrypted_id_token = encrypt_secret(id_token)
        credential.oauth_account_id = _account_id(id_token)
        credential.oauth_expires_at = expires_at
        credential.oauth_scopes = scopes.split()
        provider.enabled = True
        db.session.commit()
    except (requests.RequestException, ValueError) as exc:
        db.session.rollback()
        current_app.logger.warning("OpenAI OAuth callback failed error_type=%s", type(exc).__name__)
        return _failure_page("ChatGPT bağlantısı sırasında güvenli bir hata oluştu.", 502)

    return redirect("/?oauth=openai_success")


def refresh_if_needed(provider: Provider) -> None:
    credential = provider.credential
    if not credential or not credential.encrypted_refresh_token:
        return
    if credential.oauth_expires_at and credential.oauth_expires_at > int(time.time() * 1000) + 30_000:
        return
    from app.security.crypto import decrypt_secret

    refresh_token = decrypt_secret(credential.encrypted_refresh_token)
    if not refresh_token:
        return
    try:
        response = requests.post(
            current_app.config["OPENAI_OAUTH_TOKEN_URL"],
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "client_id": current_app.config["OPENAI_OAUTH_CLIENT_ID"],
                "refresh_token": refresh_token,
            },
            timeout=current_app.config.get("PROVIDER_TIMEOUT_SECONDS", 45),
            allow_redirects=False,
        )
        if response.status_code >= 400:
            current_app.logger.warning("OpenAI OAuth refresh failed status=%s", response.status_code)
            raise APIError("provider_authentication_failed", "ChatGPT OAuth oturumu yenilenemedi.", 502)
        data = response.json()
        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise APIError("provider_authentication_failed", "ChatGPT OAuth yenileme yanıtı eksik.", 502)
        next_refresh = data.get("refresh_token") if isinstance(data.get("refresh_token"), str) else refresh_token
        id_token = data.get("id_token") if isinstance(data.get("id_token"), str) else None
        expires_at = int(time.time() * 1000) + max(int(data.get("expires_in", 3600)), 60) * 1000
        credential.encrypted_access_token = encrypt_secret(access_token)
        credential.encrypted_refresh_token = encrypt_secret(next_refresh)
        if id_token:
            credential.encrypted_id_token = encrypt_secret(id_token)
            credential.oauth_account_id = _account_id(id_token) or credential.oauth_account_id
        credential.oauth_expires_at = expires_at
        db.session.commit()
    except APIError:
        raise
    except (requests.RequestException, ValueError, TypeError) as exc:
        db.session.rollback()
        current_app.logger.warning("OpenAI OAuth refresh failed error_type=%s", type(exc).__name__)
        raise APIError("provider_authentication_failed", "ChatGPT OAuth oturumu yenilenemedi.", 502) from None


def clear(provider: Provider) -> None:
    if not provider.credential:
        return
    credential = provider.credential
    credential.encrypted_access_token = None
    credential.encrypted_refresh_token = None
    credential.encrypted_id_token = None
    credential.oauth_account_id = None
    credential.oauth_expires_at = None
    credential.oauth_scopes = []
    db.session.commit()

"""OpenAI Codex OAuth authorization-code flow."""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import json
import secrets
import time
from urllib.parse import urlencode

import requests
from flask import current_app, redirect, request, session

from app.extensions import db
from app.models import Provider
from app.security.crypto import encrypt_secret
from app.security.errors import APIError
CODEX_SCOPES = "openid profile email offline_access api.connectors.read api.connectors.invoke"


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
    redirect_uri = current_app.config["OPENAI_OAUTH_REDIRECT_URI"]
    session["openai_oauth_pending"] = {
        "state": state,
        "verifier": verifier,
        "providerId": provider.id,
        "userId": provider.user_id,
        "createdAt": int(time.time()),
    }
    params = {
        "response_type": "code",
        "client_id": current_app.config["OPENAI_OAUTH_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "scope": current_app.config.get("OPENAI_OAUTH_SCOPES", CODEX_SCOPES),
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
                "redirect_uri": current_app.config["OPENAI_OAUTH_REDIRECT_URI"],
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

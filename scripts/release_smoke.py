#!/usr/bin/env python3
"""Live HTTP release smoke for a running Xultron server."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import requests

SENTINEL = "xultron-smoke-secret-9f7f1c8b-DO-NOT-USE"
FAIL_SENTINEL = "xultron-failure-secret-c6bb64a1-DO-NOT-USE"


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.csrf = ""
        self.seen: list[str] = []

    def request(self, method: str, path: str, *, expected: int | set[int] = 200, **kwargs: Any) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}))
        if method.upper() not in {"GET", "HEAD", "OPTIONS"} and self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        response = self.session.request(method, self.base + path, headers=headers, timeout=15, **kwargs)
        text = response.text
        self.seen.append(text)
        statuses = {expected} if isinstance(expected, int) else expected
        assert response.status_code in statuses, f"{method} {path}: {response.status_code} {text[:500]}"
        if response.headers.get("Content-Type", "").startswith("application/json") and text:
            body = response.json()
            token = body.get("csrfToken") if isinstance(body, dict) else None
            if isinstance(token, str) and token:
                self.csrf = token
        return response

    def bootstrap(self) -> dict[str, Any]:
        body = self.request("GET", "/api/v1/auth/session").json()
        self.csrf = body["csrfToken"]
        return body

    def post(self, path: str, payload: Any, expected: int | set[int] = 200) -> requests.Response:
        return self.request("POST", path, json=payload, expected=expected)

    def patch(self, path: str, payload: Any, expected: int | set[int] = 200) -> requests.Response:
        return self.request("PATCH", path, json=payload, expected=expected)

    def delete(self, path: str, payload: Any | None = None, expected: int | set[int] = 200) -> requests.Response:
        kwargs = {"json": payload} if payload is not None else {}
        return self.request("DELETE", path, expected=expected, **kwargs)


def register(api: Api, username: str, email: str) -> dict[str, Any]:
    response = api.post(
        "/api/v1/auth/register",
        {"username": username, "email": email, "password": "smoke-password-123"},
        201,
    ).json()
    return response["user"]


def create_provider(api: Api, *, name: str, kind: str, key: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {
        "name": name,
        "kind": kind,
        "adapter": "mock",
        "baseUrl": "",
        "apiKey": key,
        "model": f"mock-{kind}",
        "temperature": 0.2,
        "maxTokens": 512,
        "streaming": kind == "ai",
        "enabled": True,
        "isDefault": True,
        "config": config or {},
    }
    return api.post("/api/v1/providers", body, 201).json()["provider"]


def assert_isolated(api: Api, resource_paths: list[tuple[str, str]]) -> None:
    for method, path in resource_paths:
        response = api.request(method, path, expected={403, 404})
        assert SENTINEL not in response.text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5099")
    parser.add_argument("--database")
    parser.add_argument("--log")
    args = parser.parse_args()

    static_seen: list[str] = []
    root = requests.get(args.base + "/", timeout=10)
    assert root.status_code == 200
    assert "text/html" in root.headers.get("Content-Type", "")
    assert "X-Content-Type-Options" in root.headers
    assert "Content-Security-Policy" in root.headers
    assert "XULTRON" in root.text.upper()
    static_seen.append(root.text)
    asset_urls = re.findall(r'(?:src|href)="([^"]*?/assets/[^"]+)"', root.text)
    assert asset_urls, "No built asset URLs found in index.html"
    for path in asset_urls:
        response = requests.get(args.base + path, timeout=10)
        assert response.status_code == 200
        assert "immutable" in response.headers.get("Cache-Control", "")
        static_seen.append(response.text)
    for path in ["/manifest.webmanifest", "/sw.js", "/icons/xultron-192.png", "/icons/xultron-512.png"]:
        response = requests.get(args.base + path, timeout=10)
        assert response.status_code == 200, path
        if path.endswith((".webmanifest", ".js")):
            static_seen.append(response.text)
    spa = requests.get(args.base + "/settings/providers", timeout=10)
    assert spa.status_code == 200 and "text/html" in spa.headers.get("Content-Type", "")
    api_missing = requests.get(args.base + "/api/v1/not-a-route", timeout=10)
    assert api_missing.status_code == 404
    assert api_missing.headers.get("Content-Type", "").startswith("application/json")

    a = Api(args.base)
    assert a.bootstrap()["user"] is None
    user_a = register(a, "smoke_a", "smoke-a@example.test")
    settings = a.patch(
        "/api/v1/settings",
        {"locale": "tr", "sttLanguage": "tr", "lowDataMode": True, "theme": "darker", "accent": "violet"},
    ).json()["settings"]
    assert settings["locale"] == "tr" and settings["lowDataMode"] is True

    ai = create_provider(a, name="Smoke AI", kind="ai", key=SENTINEL, config={"reply": "Smoke yanıtı ✅"})
    assert SENTINEL not in json.dumps(ai)
    assert ai["credential"]["configured"] is True
    a.post(f"/api/v1/providers/{ai['id']}/test", {})
    models = a.post(f"/api/v1/providers/{ai['id']}/models", {}).json()["models"]
    assert models and models[0]["id"]

    stt = create_provider(a, name="Smoke STT", kind="stt", key=SENTINEL, config={"transcript": "Merhaba dünya"})
    tts = create_provider(a, name="Smoke TTS", kind="tts", key=SENTINEL, config={"voice": "alloy"})
    transcribed = a.request(
        "POST",
        "/api/v1/voice/transcribe",
        files={"audio": ("sample.webm", b"RIFF-smoke-audio", "audio/webm")},
        data={"providerId": stt["id"], "language": "tr"},
    ).json()
    assert transcribed["text"] == "Merhaba dünya"
    spoken = a.post("/api/v1/voice/synthesize", {"text": "Merhaba", "providerId": tts["id"], "voice": "alloy"})
    assert spoken.content and spoken.headers.get("Content-Type", "").startswith("audio/")

    request_id = "smoke-idempotent-1"
    payload = {"message": "Unicode deneme 🚀 مرحبا", "requestId": request_id}
    first = a.post("/api/v1/chat/messages", payload, 201).json()
    second = a.post("/api/v1/chat/messages", payload, {200, 201}).json()
    assert first == second
    conversation = first["conversation"]
    assert first["messages"][-1]["content"] == "Smoke yanıtı ✅"

    stream_id = "smoke-stream-1"
    stream = a.request(
        "POST",
        "/api/v1/chat/stream",
        json={"conversationId": conversation["id"], "message": "Akış testi", "requestId": stream_id},
    )
    assert "event: state" in stream.text and "event: done" in stream.text and "event: delta" in stream.text

    memory = a.post(
        "/api/v1/memory",
        {"title": "Smoke memory", "content": "Only user A can read this", "category": "important"},
        201,
    ).json()["memory"]
    assert a.request("GET", f"/api/v1/memory/{memory['id']}").json()["memory"]["id"] == memory["id"]

    resources = [
        ("GET", f"/api/v1/chat/conversations/{conversation['id']}"),
        ("GET", f"/api/v1/chat/conversations/{conversation['id']}/messages"),
        ("GET", f"/api/v1/memory/{memory['id']}"),
        ("GET", f"/api/v1/providers/{ai['id']}"),
        ("POST", f"/api/v1/providers/{ai['id']}/test"),
    ]

    b = Api(args.base)
    b.bootstrap()
    register(b, "smoke_b", "smoke-b@example.test")
    assert_isolated(b, resources)
    assert all(item["id"] != conversation["id"] for item in b.request("GET", "/api/v1/chat/conversations").json()["conversations"])
    assert all(item["id"] != memory["id"] for item in b.request("GET", "/api/v1/memory").json()["memories"])
    assert all(item["id"] != ai["id"] for item in b.request("GET", "/api/v1/providers").json()["providers"])

    guest = Api(args.base)
    guest.bootstrap()
    guest_response = guest.post("/api/v1/auth/guest", {}, 201).json()
    assert guest_response["user"]["isGuest"] is True
    assert_isolated(guest, resources)

    invalid = a.post(
        "/api/v1/providers",
        {
            "name": "Invalid external provider", "kind": "ai", "adapter": "openai_compatible",
            "baseUrl": "https://127.0.0.1:1/v1", "apiKey": FAIL_SENTINEL, "model": "none",
            "enabled": True, "isDefault": False, "streaming": False, "config": {},
        },
        201,
    ).json()["provider"]
    failed = a.post(f"/api/v1/providers/{invalid['id']}/test", {}, {502, 504})
    assert FAIL_SENTINEL not in failed.text
    assert "Traceback" not in failed.text and "/data/" not in failed.text
    health = a.request("GET", "/api/v1/system/health").json()
    assert health["status"] == "online"

    logout = a.post("/api/v1/auth/logout", {})
    assert logout.status_code == 200
    a.request("GET", "/api/v1/providers", expected=401)
    post_logout_guest = a.post("/api/v1/auth/guest", {}, 201).json()
    assert post_logout_guest["user"]["isGuest"] is True

    all_text = "\n".join(static_seen + a.seen + b.seen + guest.seen)
    for secret in (SENTINEL, FAIL_SENTINEL):
        assert secret not in all_text, f"Secret leaked into HTTP output: {secret}"
        if args.database:
            assert secret.encode() not in Path(args.database).read_bytes(), f"Secret leaked into database: {secret}"
        if args.log and Path(args.log).exists():
            assert secret not in Path(args.log).read_text(errors="replace"), f"Secret leaked into server log: {secret}"

    if args.database:
        with sqlite3.connect(args.database) as db:
            db.execute("PRAGMA foreign_keys = ON")
            assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            count = db.execute("select count(*) from provider_credentials").fetchone()[0]
            assert count >= 4

    print("Live HTTP release smoke passed: static/PWA, auth, providers, chat/SSE, voice, memory, isolation, secrets, logout recovery.")


if __name__ == "__main__":
    main()

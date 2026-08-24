import json
import time
from typing import Iterable
from urllib.parse import urlparse

import requests
from flask import current_app

from app.providers.base import ProviderConfig, ProviderFailure
from app.security.redaction import redact


class MockAdapter:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg

    def test(self):
        if (self.cfg.config or {}).get("fail"):
            raise ProviderFailure("provider_test_failed", "Provider test failed safely.", 502)
        return {"ok": True, "latencyMs": 1, "message": "Mock provider is available."}

    def models(self):
        return [{"id": self.cfg.model or "mock-model", "label": self.cfg.model or "Mock Model"}]

    def complete(self, messages):
        last = messages[-1]["content"] if messages else ""
        return (self.cfg.config or {}).get("reply") or f"Mock response: {last}"

    def stream(self, messages) -> Iterable[str]:
        for token in self.complete(messages).split(" "):
            yield token + " "

    def transcribe(self, audio: bytes, filename: str, language: str | None):
        if not audio:
            raise ProviderFailure("invalid_audio", "Audio is empty.", 422)
        return {"text": (self.cfg.config or {}).get("transcript", "mock transcript"), "language": language}

    def synthesize(self, text: str, voice: str | None):
        return (f"MOCK-AUDIO:{voice or 'default'}:{text}".encode(), "audio/plain")


class OpenAICompatibleAdapter:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.timeout = current_app.config.get("PROVIDER_TIMEOUT_SECONDS", 20)

    @property
    def base(self):
        if not self.cfg.base_url:
            raise ProviderFailure("provider_invalid", "Provider base URL is required.", 422)
        parsed = urlparse(self.cfg.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ProviderFailure("provider_invalid", "Provider base URL is invalid.", 422)
        return self.cfg.base_url.rstrip("/")

    def headers(self):
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        return headers

    def _safe_raise(self, exc, code="provider_request_failed"):
        raise ProviderFailure(code, "Provider request failed safely.", 502, retryable=True)

    def _bound_text(self, value, empty_code="provider_empty_response"):
        if not isinstance(value, str):
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502, True)
        value = value.strip()
        if not value:
            raise ProviderFailure(empty_code, "Provider returned an empty response.", 502, True)
        return value[: current_app.config.get("MAX_PROVIDER_TEXT_CHARS", 24000)]

    def test(self):
        start = time.monotonic()
        try:
            r = requests.get(f"{self.base}/models", headers=self.headers(), timeout=self.timeout)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        if r.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by the provider.", 502)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        return {"ok": True, "latencyMs": int((time.monotonic() - start) * 1000), "message": "Connection succeeded."}

    def models(self):
        try:
            r = requests.get(f"{self.base}/models", headers=self.headers(), timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except Exception as exc:
            self._safe_raise(exc, "provider_model_discovery_failed")
        raw = data.get("data", data.get("models", [])) if isinstance(data, dict) else []
        if not isinstance(raw, list):
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502, True)
        models = []
        for item in raw[:500]:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name") or item.get("model")
            else:
                model_id = item
            if isinstance(model_id, str) and model_id.strip():
                safe_id = model_id.strip()[:160]
                models.append({"id": safe_id, "label": safe_id})
        return models

    def complete(self, messages):
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature if self.cfg.temperature is not None else 0.3,
            "max_tokens": self.cfg.max_tokens or 800,
            "stream": False,
        }
        try:
            r = requests.post(f"{self.base}/chat/completions", headers=self.headers(), json=payload, timeout=self.timeout)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        if r.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by the provider.", 502)
        if r.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "Provider rate limit reached.", 502, True)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        try:
            data = r.json()
            choices = data.get("choices") if isinstance(data, dict) else None
            first = choices[0] if isinstance(choices, list) and choices else None
            message = first.get("message") if isinstance(first, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
        except Exception:
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502, True)
        return self._bound_text(content)

    def stream(self, messages) -> Iterable[str]:
        # Non-stream fallback keeps SSE contract stable even when provider streaming is absent.
        text = self.complete(messages)
        for token in text.split(" "):
            yield token + " "

    def transcribe(self, audio: bytes, filename: str, language: str | None):
        files = {"file": (filename or "audio.webm", audio), "model": (None, self.cfg.model or "whisper-1")}
        if language:
            files["language"] = (None, language)
        try:
            r = requests.post(f"{self.base}/audio/transcriptions", headers={k: v for k, v in self.headers().items() if k != "Content-Type"}, files=files, timeout=self.timeout)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        try:
            data = r.json()
        except Exception:
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502)
        if not isinstance(data, dict):
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502)
        text = self._bound_text(data.get("text"))
        lang = data.get("language", language)
        if lang is not None and not isinstance(lang, str):
            lang = language
        return {"text": text, "language": lang}

    def synthesize(self, text: str, voice: str | None):
        payload = {"model": self.cfg.model or "tts-1", "input": text, "voice": voice or self.cfg.config.get("voice") or "alloy"}
        if self.cfg.config.get("speed") is not None:
            payload["speed"] = self.cfg.config["speed"]
        try:
            r = requests.post(f"{self.base}/audio/speech", headers=self.headers(), json=payload, timeout=self.timeout)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        if not r.content:
            raise ProviderFailure("provider_empty_response", "Provider returned an empty response.", 502, True)
        max_bytes = current_app.config.get("MAX_AUDIO_BYTES", 5242880)
        if len(r.content) > max_bytes:
            raise ProviderFailure("provider_response_too_large", "Provider audio response is too large.", 502)
        media_type = (r.headers.get("Content-Type") or "audio/mpeg").split(";", 1)[0]
        if not media_type.startswith("audio/"):
            media_type = "audio/mpeg"
        return r.content, media_type


class CustomHTTPAdapter(OpenAICompatibleAdapter):
    def complete(self, messages):
        payload = {"messages": messages, "model": self.cfg.model, "config": self.cfg.config or {}}
        try:
            r = requests.post(self.base, headers=self.headers(), json=payload, timeout=self.timeout)
            if r.status_code in {401, 403}:
                raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by the provider.", 502)
            if r.status_code == 429:
                raise ProviderFailure("provider_rate_limited", "Provider rate limit reached.", 502, True)
            if r.status_code >= 400:
                raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
            data = r.json()
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except ProviderFailure:
            raise
        except Exception as exc:
            self._safe_raise(exc)
        if not isinstance(data, dict):
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502, True)
        text = data.get("text") or data.get("content") or data.get("response")
        return self._bound_text(text)

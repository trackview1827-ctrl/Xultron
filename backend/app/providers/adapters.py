import json
import time
from typing import Iterable

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
        return self.cfg.base_url.rstrip("/")

    def headers(self):
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        return headers

    def _safe_raise(self, exc, code="provider_request_failed"):
        msg = redact(str(exc))
        raise ProviderFailure(code, f"Provider request failed: {msg}", 502, retryable=True)

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
        return [{"id": str(m.get("id", m)), "label": str(m.get("id", m))} for m in raw]

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
            content = data["choices"][0]["message"]["content"]
        except Exception:
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502, True)
        if not content:
            raise ProviderFailure("provider_empty_response", "Provider returned an empty response.", 502, True)
        return content

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
        return {"text": data.get("text", ""), "language": data.get("language", language)}

    def synthesize(self, text: str, voice: str | None):
        payload = {"model": self.cfg.model or "tts-1", "input": text, "voice": voice or self.cfg.config.get("voice") or "alloy"}
        try:
            r = requests.post(f"{self.base}/audio/speech", headers=self.headers(), json=payload, timeout=self.timeout)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        return r.content, r.headers.get("Content-Type", "audio/mpeg")


class CustomHTTPAdapter(OpenAICompatibleAdapter):
    def complete(self, messages):
        payload = {"messages": messages, "model": self.cfg.model, "config": self.cfg.config or {}}
        try:
            r = requests.post(self.base, headers=self.headers(), json=payload, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except Exception as exc:
            self._safe_raise(exc)
        text = data.get("text") or data.get("content") or data.get("response")
        if not text:
            raise ProviderFailure("provider_empty_response", "Provider returned an empty response.", 502, True)
        return text

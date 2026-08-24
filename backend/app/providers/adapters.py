import json
import time
from typing import Iterable
from urllib.parse import quote, urlparse

import requests
from flask import current_app

from app.providers.base import ProviderConfig, ProviderFailure


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

    def _check_response(self, response, max_bytes):
        if 300 <= response.status_code < 400:
            raise ProviderFailure("provider_redirect_blocked", "Provider redirect was blocked.", 502, True)
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    raise ProviderFailure("provider_response_too_large", "Provider response is too large.", 502)
            except ValueError:
                pass

    def _read_bounded(self, response, max_bytes=None):
        if max_bytes is None:
            max_bytes = current_app.config.get("MAX_PROVIDER_RESPONSE_BYTES", 1048576)
        try:
            self._check_response(response, max_bytes)
            content = bytearray()
            iterator = getattr(response, "iter_content", None)
            chunks = iterator(chunk_size=65536) if callable(iterator) else [getattr(response, "content", b"") or b""]
            for chunk in chunks:
                if not chunk:
                    continue
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise ProviderFailure("provider_response_too_large", "Provider response is too large.", 502)
            return bytes(content)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

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
            r = requests.get(f"{self.base}/models", headers=self.headers(), timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        self._read_bounded(r)
        if r.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by the provider.", 502)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        return {"ok": True, "latencyMs": int((time.monotonic() - start) * 1000), "message": "Connection succeeded."}

    def models(self):
        try:
            r = requests.get(f"{self.base}/models", headers=self.headers(), timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc, "provider_model_discovery_failed")
        body = self._read_bounded(r)
        if r.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by the provider.", 502)
        if r.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "Provider rate limit reached.", 502, True)
        if r.status_code >= 400:
            raise ProviderFailure("provider_model_discovery_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        try:
            data = json.loads(body.decode(getattr(r, "encoding", None) or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, LookupError):
            raise ProviderFailure("provider_malformed_response", "Provider returned malformed response.", 502, True)
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
            r = requests.post(f"{self.base}/chat/completions", headers=self.headers(), json=payload, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        body = self._read_bounded(r)
        if r.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by the provider.", 502)
        if r.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "Provider rate limit reached.", 502, True)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        try:
            data = json.loads(body.decode(getattr(r, "encoding", None) or "utf-8"))
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
            r = requests.post(f"{self.base}/audio/transcriptions", headers={k: v for k, v in self.headers().items() if k != "Content-Type"}, files=files, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        body = self._read_bounded(r)
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        try:
            data = json.loads(body.decode(getattr(r, "encoding", None) or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, LookupError):
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
            r = requests.post(f"{self.base}/audio/speech", headers=self.headers(), json=payload, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Provider request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        audio = self._read_bounded(r, current_app.config.get("MAX_AUDIO_BYTES", 5242880))
        if r.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
        if not audio:
            raise ProviderFailure("provider_empty_response", "Provider returned an empty response.", 502, True)
        media_type = (r.headers.get("Content-Type") or "audio/mpeg").split(";", 1)[0]
        if not media_type.startswith("audio/"):
            media_type = "audio/mpeg"
        return audio, media_type


class GeminiAdapter(OpenAICompatibleAdapter):
    """Google Gemini Generative Language REST adapter for AI completion."""

    @property
    def base(self):
        configured = self.cfg.base_url or "https://generativelanguage.googleapis.com/v1beta"
        parsed = urlparse(configured)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ProviderFailure("provider_invalid", "Gemini base URL must be a valid HTTPS URL.", 422)
        return configured.rstrip("/")

    def headers(self):
        if not self.cfg.api_key:
            raise ProviderFailure("provider_authentication_failed", "Gemini API key is required.", 422)
        return {"Content-Type": "application/json", "x-goog-api-key": self.cfg.api_key}

    def _json_response(self, response, failure_code="provider_request_failed"):
        body = self._read_bounded(response)
        if response.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by Gemini.", 502)
        if response.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "Gemini rate limit reached.", 502, True)
        if response.status_code >= 400:
            raise ProviderFailure(failure_code, f"Gemini returned HTTP {response.status_code}.", 502, response.status_code >= 500)
        try:
            data = json.loads(body.decode(getattr(response, "encoding", None) or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, LookupError):
            raise ProviderFailure("provider_malformed_response", "Gemini returned malformed response.", 502, True)
        if not isinstance(data, dict):
            raise ProviderFailure("provider_malformed_response", "Gemini returned malformed response.", 502, True)
        return data

    def models(self):
        try:
            response = requests.get(f"{self.base}/models", headers=self.headers(), timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Gemini request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc, "provider_model_discovery_failed")
        data = self._json_response(response, "provider_model_discovery_failed")
        raw = data.get("models", [])
        if not isinstance(raw, list):
            raise ProviderFailure("provider_malformed_response", "Gemini returned malformed model data.", 502, True)
        models = []
        for item in raw[:500]:
            if not isinstance(item, dict):
                continue
            methods = item.get("supportedGenerationMethods", [])
            if isinstance(methods, list) and "generateContent" not in methods:
                continue
            model_id = item.get("name")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            model_id = model_id.strip().removeprefix("models/")[:160]
            label = item.get("displayName") if isinstance(item.get("displayName"), str) else model_id
            models.append({"id": model_id, "label": label[:160]})
        return models

    def test(self):
        start = time.monotonic()
        self.models()
        return {"ok": True, "latencyMs": int((time.monotonic() - start) * 1000), "message": "Gemini bağlantısı başarılı."}

    def complete(self, messages):
        model = (self.cfg.model or "gemini-2.5-flash").removeprefix("models/")
        safe_model = quote(model, safe="-._")
        system_parts = []
        contents = []
        for message in messages:
            content = message.get("content") if isinstance(message, dict) else None
            role = message.get("role") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                continue
            if role == "system":
                system_parts.append({"text": content})
            else:
                contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": content}]})
        if not contents:
            raise ProviderFailure("provider_invalid", "Gemini requires at least one message.", 422)
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.cfg.temperature if self.cfg.temperature is not None else 0.3,
                "maxOutputTokens": self.cfg.max_tokens or 800,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        try:
            response = requests.post(f"{self.base}/models/{safe_model}:generateContent", headers=self.headers(), json=payload, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Gemini request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        data = self._json_response(response)
        candidates = data.get("candidates")
        first = candidates[0] if isinstance(candidates, list) and candidates else None
        content = first.get("content") if isinstance(first, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)) if isinstance(parts, list) else ""
        return self._bound_text(text)


class CustomHTTPAdapter(OpenAICompatibleAdapter):
    def complete(self, messages):
        payload = {"messages": messages, "model": self.cfg.model, "config": self.cfg.config or {}}
        try:
            r = requests.post(self.base, headers=self.headers(), json=payload, timeout=self.timeout, allow_redirects=False, stream=True)
            body = self._read_bounded(r)
            if r.status_code in {401, 403}:
                raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by the provider.", 502)
            if r.status_code == 429:
                raise ProviderFailure("provider_rate_limited", "Provider rate limit reached.", 502, True)
            if r.status_code >= 400:
                raise ProviderFailure("provider_request_failed", f"Provider returned HTTP {r.status_code}.", 502, r.status_code >= 500)
            data = json.loads(body.decode(getattr(r, "encoding", None) or "utf-8"))
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

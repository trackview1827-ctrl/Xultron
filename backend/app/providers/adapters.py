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
        return value[: current_app.config.get("MAX_PROVIDER_TEXT_CHARS", 200000)]

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
            "max_tokens": self.cfg.max_tokens or current_app.config.get("DEFAULT_AI_MAX_TOKENS", 4096),
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


class ElevenLabsAdapter(OpenAICompatibleAdapter):
    """Official ElevenLabs REST adapter for speech-to-text and text-to-speech."""

    _DEFAULT_BASE = "https://api.elevenlabs.io/v1"
    _STT_MODELS = ("scribe_v2", "scribe_v1")

    @property
    def base(self):
        configured = (self.cfg.base_url or self._DEFAULT_BASE).rstrip("/")
        parsed = urlparse(configured)
        if parsed.scheme != "https" or parsed.netloc != "api.elevenlabs.io" or parsed.username or parsed.password:
            raise ProviderFailure("provider_invalid", "ElevenLabs base URL must be https://api.elevenlabs.io/v1.", 422)
        if parsed.path in {"", "/"}:
            return self._DEFAULT_BASE
        if parsed.path.rstrip("/") != "/v1" or parsed.query or parsed.fragment:
            raise ProviderFailure("provider_invalid", "ElevenLabs base URL must be https://api.elevenlabs.io/v1.", 422)
        return configured

    def headers(self):
        if not self.cfg.api_key:
            raise ProviderFailure("provider_authentication_failed", "ElevenLabs API key is required.", 422)
        return {"xi-api-key": self.cfg.api_key}

    def _json_response(self, response, failure_code="provider_request_failed"):
        body = self._read_bounded(response)
        if response.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by ElevenLabs.", 502)
        if response.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "ElevenLabs rate limit reached.", 502, True)
        if response.status_code >= 400:
            raise ProviderFailure(failure_code, f"ElevenLabs returned HTTP {response.status_code}.", 502, response.status_code >= 500)
        try:
            data = json.loads(body.decode(getattr(response, "encoding", None) or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, LookupError):
            raise ProviderFailure("provider_malformed_response", "ElevenLabs returned malformed response.", 502, True)
        if not isinstance(data, (dict, list)):
            raise ProviderFailure("provider_malformed_response", "ElevenLabs returned malformed response.", 502, True)
        return data

    def test(self):
        start = time.monotonic()
        self._list_remote_models()
        return {"ok": True, "latencyMs": int((time.monotonic() - start) * 1000), "message": "ElevenLabs bağlantısı başarılı."}

    def _list_remote_models(self):
        try:
            response = requests.get(f"{self.base}/models", headers=self.headers(), timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "ElevenLabs request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc, "provider_model_discovery_failed")
        return self._json_response(response, "provider_model_discovery_failed")

    def models(self):
        if self.cfg.kind == "stt":
            return [{"id": model, "label": f"ElevenLabs {model}"} for model in self._STT_MODELS]
        raw = self._list_remote_models()
        if not isinstance(raw, list):
            raise ProviderFailure("provider_malformed_response", "ElevenLabs returned malformed model data.", 502, True)
        models = []
        for item in raw[:500]:
            if not isinstance(item, dict) or not isinstance(item.get("model_id"), str):
                continue
            if self.cfg.kind == "tts" and item.get("can_do_text_to_speech") is False:
                continue
            model_id = item["model_id"].strip()[:160]
            if model_id:
                label = item.get("name") if isinstance(item.get("name"), str) else model_id
                models.append({"id": model_id, "label": label[:160]})
        return models

    def transcribe(self, audio: bytes, filename: str, language: str | None):
        if not audio:
            raise ProviderFailure("invalid_audio", "Audio is empty.", 422)
        data = {"model_id": self.cfg.model or "scribe_v2"}
        language_code = language or self.cfg.config.get("language")
        if language_code and language_code != "auto":
            data["language_code"] = language_code
        files = {"file": (filename or "audio.webm", audio)}
        try:
            response = requests.post(f"{self.base}/speech-to-text", headers=self.headers(), files=files, data=data, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "ElevenLabs request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        payload = self._json_response(response)
        if not isinstance(payload, dict):
            raise ProviderFailure("provider_malformed_response", "ElevenLabs returned malformed transcript data.", 502, True)
        text = self._bound_text(payload.get("text"))
        detected = payload.get("language_code") or language
        return {"text": text, "language": detected if isinstance(detected, str) else None}

    def synthesize(self, text: str, voice: str | None):
        voice_id = voice or self.cfg.config.get("voice") or self.cfg.config.get("voiceId")
        if not isinstance(voice_id, str) or not voice_id.strip():
            raise ProviderFailure("provider_invalid", "ElevenLabs voice ID is required for synthesis.", 422)
        payload = {"text": text, "model_id": self.cfg.model or "eleven_multilingual_v2"}
        language_code = self.cfg.config.get("language")
        if isinstance(language_code, str) and language_code and language_code != "auto":
            payload["language_code"] = language_code
        speed = self.cfg.config.get("speed")
        if speed is not None:
            if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not 0.7 <= float(speed) <= 1.2:
                raise ProviderFailure("provider_invalid", "ElevenLabs speed must be between 0.7 and 1.2.", 422)
            payload["voice_settings"] = {"speed": float(speed)}
        output_format = self.cfg.config.get("outputFormat", "mp3_44100_128")
        if not isinstance(output_format, str) or len(output_format) > 40:
            raise ProviderFailure("provider_invalid", "ElevenLabs output format is invalid.", 422)
        try:
            response = requests.post(
                f"{self.base}/text-to-speech/{quote(voice_id.strip(), safe='')}",
                params={"output_format": output_format},
                headers={**self.headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "ElevenLabs request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        audio = self._read_bounded(response, current_app.config.get("MAX_AUDIO_BYTES", 5242880))
        if response.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by ElevenLabs.", 502)
        if response.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "ElevenLabs rate limit reached.", 502, True)
        if response.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"ElevenLabs returned HTTP {response.status_code}.", 502, response.status_code >= 500)
        if not audio:
            raise ProviderFailure("provider_empty_response", "ElevenLabs returned empty audio.", 502, True)
        media_type = (response.headers.get("Content-Type") or "audio/mpeg").split(";", 1)[0]
        return audio, media_type if media_type.startswith("audio/") else "audio/mpeg"


class WhisperCppAdapter(OpenAICompatibleAdapter):
    """Local whisper.cpp HTTP server adapter for low-data STT."""

    @property
    def base(self):
        configured = (self.cfg.base_url or "http://127.0.0.1:8766").rstrip("/")
        parsed = urlparse(configured)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ProviderFailure("provider_invalid", "whisper.cpp base URL must point to localhost.", 422)
        return configured

    def headers(self):
        return {}

    def test(self):
        start = time.monotonic()
        try:
            response = requests.get(self.base, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "whisper.cpp request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        self._read_bounded(response, 65536)
        if response.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"whisper.cpp returned HTTP {response.status_code}.", 502, True)
        return {"ok": True, "latencyMs": int((time.monotonic() - start) * 1000), "message": "whisper.cpp bağlantısı başarılı."}

    def models(self):
        return [{"id": self.cfg.model or "tiny", "label": f"whisper.cpp {self.cfg.model or 'tiny'}"}]

    def transcribe(self, audio: bytes, filename: str, language: str | None):
        if not audio:
            raise ProviderFailure("invalid_audio", "Audio is empty.", 422)
        data = {"response_format": "json"}
        if language and language != "auto":
            data["language"] = language
        try:
            response = requests.post(f"{self.base}/inference", headers=self.headers(), files={"file": (filename or "audio.webm", audio)}, data=data, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "whisper.cpp request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        body = self._read_bounded(response)
        if response.status_code >= 400:
            raise ProviderFailure("provider_request_failed", f"whisper.cpp returned HTTP {response.status_code}.", 502, response.status_code >= 500)
        try:
            payload = json.loads(body.decode(getattr(response, "encoding", None) or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, LookupError):
            raise ProviderFailure("provider_malformed_response", "whisper.cpp returned malformed transcript data.", 502, True)
        if not isinstance(payload, dict):
            raise ProviderFailure("provider_malformed_response", "whisper.cpp returned malformed transcript data.", 502, True)
        return {"text": self._bound_text(payload.get("text")), "language": language}


class CodexOAuthAdapter(OpenAICompatibleAdapter):
    """OpenAI Codex OAuth transport for ChatGPT subscription accounts."""

    @property
    def base(self):
        if self.cfg.auth_mode != "codex_oauth" or not self.cfg.access_token:
            raise ProviderFailure("provider_authentication_failed", "Codex OAuth bağlantısı kurulmamış.", 422)
        return "https://chatgpt.com/backend-api/codex"

    def headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.cfg.access_token}",
            "originator": "codex_cli_rs",
        }
        if self.cfg.account_id:
            headers["chatgpt-account-id"] = self.cfg.account_id
        return headers

    def _json_response(self, response, failure_code="provider_request_failed"):
        body = self._read_bounded(response)
        if response.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "ChatGPT OAuth oturumu reddedildi.", 502)
        if response.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "ChatGPT rate limit reached.", 502, True)
        if response.status_code >= 400:
            raise ProviderFailure(failure_code, f"ChatGPT returned HTTP {response.status_code}.", 502, response.status_code >= 500)
        try:
            data = json.loads(body.decode(getattr(response, "encoding", None) or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, LookupError):
            raise ProviderFailure("provider_malformed_response", "ChatGPT returned malformed response.", 502, True)
        if not isinstance(data, dict):
            raise ProviderFailure("provider_malformed_response", "ChatGPT returned malformed response.", 502, True)
        return data

    def models(self):
        try:
            response = requests.get(
                f"{self.base}/models?client_version=1.0.0",
                headers=self.headers(), timeout=self.timeout, allow_redirects=False, stream=True,
            )
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "ChatGPT request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc, "provider_model_discovery_failed")
        data = self._json_response(response, "provider_model_discovery_failed")
        raw = data.get("data", data.get("models", []))
        if not isinstance(raw, list):
            raise ProviderFailure("provider_malformed_response", "ChatGPT returned malformed model data.", 502, True)
        models = []
        for item in raw[:500]:
            model_id = item.get("id") or item.get("slug") or item.get("model") if isinstance(item, dict) else item
            if isinstance(model_id, str) and model_id.strip():
                model_id = model_id.strip()[:160]
                models.append({"id": model_id, "label": model_id})
        return models

    def test(self):
        start = time.monotonic()
        self.models()
        return {"ok": True, "latencyMs": int((time.monotonic() - start) * 1000), "message": "ChatGPT OAuth bağlantısı başarılı."}

    def complete(self, messages):
        input_items = []
        instructions = []
        for message in messages:
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                continue
            content = message["content"].strip()
            if not content:
                continue
            if message.get("role") == "system":
                instructions.append(content)
            else:
                input_items.append({"role": "assistant" if message.get("role") == "assistant" else "user", "content": content})
        if not input_items:
            raise ProviderFailure("provider_invalid", "ChatGPT requires at least one user message.", 422)
        payload = {
            "model": self.cfg.model or "gpt-5-codex",
            "instructions": "\n\n".join(instructions),
            "input": input_items,
            "stream": False,
            "store": False,
        }
        try:
            response = requests.post(
                f"{self.base}/responses", headers=self.headers(), json=payload,
                timeout=self.timeout, allow_redirects=False, stream=True,
            )
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "ChatGPT request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        data = self._json_response(response)
        output_text = data.get("output_text")
        if not isinstance(output_text, str):
            parts = []
            for item in data.get("output", []) if isinstance(data.get("output"), list) else []:
                for block in item.get("content", []) if isinstance(item, dict) and isinstance(item.get("content"), list) else []:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        parts.append(block["text"])
            output_text = "".join(parts)
        return self._bound_text(output_text)


class AnthropicAdapter(OpenAICompatibleAdapter):
    """Anthropic Messages REST adapter for Claude models."""

    @property
    def base(self):
        configured = self.cfg.base_url or "https://api.anthropic.com"
        parsed = urlparse(configured)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ProviderFailure("provider_invalid", "Anthropic base URL must be a valid HTTPS URL.", 422)
        return configured.rstrip("/")

    def headers(self):
        if not self.cfg.api_key:
            raise ProviderFailure("provider_authentication_failed", "Anthropic API key is required.", 422)
        return {
            "Content-Type": "application/json",
            "x-api-key": self.cfg.api_key,
            "anthropic-version": "2023-06-01",
        }

    def _json_response(self, response, failure_code="provider_request_failed"):
        body = self._read_bounded(response)
        if response.status_code in {401, 403}:
            raise ProviderFailure("provider_authentication_failed", "Authentication was rejected by Anthropic.", 502)
        if response.status_code == 429:
            raise ProviderFailure("provider_rate_limited", "Anthropic rate limit reached.", 502, True)
        if response.status_code >= 400:
            raise ProviderFailure(failure_code, f"Anthropic returned HTTP {response.status_code}.", 502, response.status_code >= 500)
        try:
            data = json.loads(body.decode(getattr(response, "encoding", None) or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, LookupError):
            raise ProviderFailure("provider_malformed_response", "Anthropic returned malformed response.", 502, True)
        if not isinstance(data, dict):
            raise ProviderFailure("provider_malformed_response", "Anthropic returned malformed response.", 502, True)
        return data

    def models(self):
        try:
            response = requests.get(f"{self.base}/v1/models", headers=self.headers(), timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Anthropic request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc, "provider_model_discovery_failed")
        data = self._json_response(response, "provider_model_discovery_failed")
        raw = data.get("data", [])
        if not isinstance(raw, list):
            raise ProviderFailure("provider_malformed_response", "Anthropic returned malformed model data.", 502, True)
        models = []
        for item in raw[:500]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            model_id = item["id"].strip()[:160]
            if not model_id:
                continue
            label = item.get("display_name") if isinstance(item.get("display_name"), str) else model_id
            models.append({"id": model_id, "label": label[:160]})
        return models

    def test(self):
        start = time.monotonic()
        self.models()
        return {"ok": True, "latencyMs": int((time.monotonic() - start) * 1000), "message": "Anthropic bağlantısı başarılı."}

    def complete(self, messages):
        system_parts = []
        conversation = []
        for message in messages:
            content = message.get("content") if isinstance(message, dict) else None
            role = message.get("role") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                continue
            if role == "system":
                system_parts.append(content)
            else:
                conversation.append({"role": "assistant" if role == "assistant" else "user", "content": content})
        if not conversation:
            raise ProviderFailure("provider_invalid", "Anthropic requires at least one message.", 422)
        payload = {
            "model": self.cfg.model or "claude-sonnet-5",
            "messages": conversation,
            "temperature": self.cfg.temperature if self.cfg.temperature is not None else 0.3,
            "max_tokens": self.cfg.max_tokens or current_app.config.get("DEFAULT_AI_MAX_TOKENS", 4096),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        try:
            response = requests.post(f"{self.base}/v1/messages", headers=self.headers(), json=payload, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ProviderFailure("provider_timeout", "Anthropic request timed out.", 504, True)
        except requests.RequestException as exc:
            self._safe_raise(exc)
        data = self._json_response(response)
        blocks = data.get("content", [])
        text = "".join(block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text") if isinstance(blocks, list) else ""
        return self._bound_text(text)


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
                "maxOutputTokens": self.cfg.max_tokens or current_app.config.get("DEFAULT_AI_MAX_TOKENS", 4096),
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

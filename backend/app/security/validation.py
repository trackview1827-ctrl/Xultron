from __future__ import annotations

import re
from urllib.parse import urlparse

from app.security.errors import APIError


USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,40}$")
SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|authorization|password|secret|token|credential)")
SECRET_VALUE_RE = re.compile(r"(?i)(bearer\s+|sk-[A-Za-z0-9_\-]{8,}|xox[baprs]-|ghp_[A-Za-z0-9_]{8,})")


def require_object(data, name: str = "body") -> dict:
    if not isinstance(data, dict):
        raise APIError("validation_failed", f"{name} must be an object.", 422)
    return data


def string_field(data: dict, key: str, *, required=False, min_len=0, max_len=500, default=None) -> str | None:
    if key not in data:
        if required:
            raise APIError("validation_failed", f"{key} is required.", 422)
        return default
    value = data[key]
    if value is None:
        if required:
            raise APIError("validation_failed", f"{key} is required.", 422)
        return default
    if not isinstance(value, str):
        raise APIError("validation_failed", f"{key} must be a string.", 422)
    value = value.strip()
    if len(value) < min_len:
        raise APIError("validation_failed", f"{key} is too short.", 422)
    if len(value) > max_len:
        raise APIError("validation_failed", f"{key} is too long.", 422)
    return value


def bool_field(data: dict, key: str, *, required=False, default=None) -> bool | None:
    if key not in data:
        if required:
            raise APIError("validation_failed", f"{key} is required.", 422)
        return default
    if not isinstance(data[key], bool):
        raise APIError("validation_failed", f"{key} must be a boolean.", 422)
    return data[key]


def int_field(data: dict, key: str, *, min_value: int, max_value: int, default=None) -> int | None:
    if key not in data or data[key] is None:
        return default
    if not isinstance(data[key], int) or isinstance(data[key], bool):
        raise APIError("validation_failed", f"{key} must be an integer.", 422)
    if data[key] < min_value or data[key] > max_value:
        raise APIError("validation_failed", f"{key} is out of range.", 422)
    return data[key]


def float_field(data: dict, key: str, *, min_value: float, max_value: float, default=None) -> float | None:
    if key not in data or data[key] is None:
        return default
    if not isinstance(data[key], (int, float)) or isinstance(data[key], bool):
        raise APIError("validation_failed", f"{key} must be a number.", 422)
    value = float(data[key])
    if value < min_value or value > max_value:
        raise APIError("validation_failed", f"{key} is out of range.", 422)
    return value


def enum_field(data: dict, key: str, allowed: set[str], *, default=None, required=False) -> str | None:
    value = string_field(data, key, required=required, max_len=80, default=default)
    if value is None:
        return None
    if value not in allowed:
        raise APIError("validation_failed", f"{key} is invalid.", 422)
    return value


def normalize_username(value: object) -> str:
    if not isinstance(value, str):
        raise APIError("validation_failed", "username must be a string.", 422)
    username = value.strip().lower()
    if not USERNAME_RE.fullmatch(username):
        raise APIError("validation_failed", "Username must be 3-40 lowercase letters, numbers, dots, underscores or hyphens.", 422)
    return username


def normalize_email(value: object) -> str:
    if not isinstance(value, str):
        raise APIError("validation_failed", "email must be a string.", 422)
    email = value.strip().lower()
    if not email or len(email) > 255 or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise APIError("validation_failed", "A valid email is required.", 422)
    return email


def validate_base_url(value: str | None) -> str | None:
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise APIError("validation_failed", "baseUrl must be a string.", 422)
    url = value.strip()
    if len(url) > 500:
        raise APIError("validation_failed", "baseUrl is too long.", 422)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise APIError("validation_failed", "baseUrl must be an HTTP(S) URL.", 422)
    if parsed.username or parsed.password:
        raise APIError("validation_failed", "baseUrl must not contain credentials.", 422)
    if parsed.fragment:
        raise APIError("validation_failed", "baseUrl must not contain a fragment.", 422)
    return url.rstrip("/")


def ensure_no_secret_like_keys(config, *, depth: int = 0):
    if depth > 4:
        raise APIError("validation_failed", "Provider config is too deeply nested.", 422)
    if isinstance(config, dict):
        if len(config) > 30:
            raise APIError("validation_failed", "Provider config has too many keys.", 422)
        for key, value in config.items():
            if not isinstance(key, str) or len(key) > 80:
                raise APIError("validation_failed", "Provider config keys must be short strings.", 422)
            if SECRET_KEY_RE.search(key):
                raise APIError("validation_failed", "Provider config cannot contain secret-like keys. Use apiKey.", 422)
            ensure_no_secret_like_keys(value, depth=depth + 1)
        return
    if isinstance(config, list):
        if len(config) > 50:
            raise APIError("validation_failed", "Provider config lists are too long.", 422)
        for value in config:
            ensure_no_secret_like_keys(value, depth=depth + 1)
        return
    if isinstance(config, str):
        if len(config) > 2000:
            raise APIError("validation_failed", "Provider config string is too long.", 422)
        if SECRET_VALUE_RE.search(config):
            raise APIError("validation_failed", "Provider config cannot contain secret-like values. Use apiKey.", 422)
        return
    if config is not None and not isinstance(config, (bool, int, float)):
        raise APIError("validation_failed", "Provider config values must be JSON primitives, arrays or objects.", 422)

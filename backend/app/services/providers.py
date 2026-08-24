from app.extensions import db
from app.models import Provider, ProviderCredential
from app.providers.base import ProviderFailure
from app.providers.registry import KINDS, build
from app.security.crypto import encrypt_secret, mask_secret
from app.security.errors import APIError
from app.security.validation import (
    bool_field,
    ensure_no_secret_like_keys,
    enum_field,
    float_field,
    int_field,
    require_object,
    string_field,
    validate_base_url,
)

ADAPTERS = {"openai_compatible", "custom_http", "local_http", "mock"}
PUBLIC_CONFIG_KEYS = {
    "reply",
    "transcript",
    "voice",
    "voiceId",
    "speed",
    "language",
    "responsePath",
    "textPath",
    "fail",
}


def _owned(provider_id, user_id):
    provider = db.session.get(Provider, provider_id)
    if not provider:
        raise APIError("not_found", "Provider was not found.", 404)
    if provider.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this provider.", 403)
    return provider


def validate_payload(data, partial=False):
    data = require_object(data)
    out = {}
    if not partial:
        for required in ["name", "kind", "adapter"]:
            if required not in data or not data.get(required):
                raise APIError("validation_failed", f"{required} is required.", 422)
    if "name" in data:
        out["name"] = string_field(data, "name", required=True, min_len=1, max_len=120)
    if "kind" in data:
        out["kind"] = enum_field(data, "kind", KINDS, required=not partial)
    if "adapter" in data:
        out["adapter"] = enum_field(data, "adapter", ADAPTERS, required=not partial)
    if "baseUrl" in data:
        out["base_url"] = validate_base_url(data.get("baseUrl"))
    if "model" in data:
        out["model"] = string_field(data, "model", max_len=160, default=None)
    if "temperature" in data:
        out["temperature"] = float_field(data, "temperature", min_value=0, max_value=2)
    if "maxTokens" in data:
        out["max_tokens"] = int_field(data, "maxTokens", min_value=1, max_value=32000)
    if "streaming" in data:
        out["streaming"] = bool_field(data, "streaming")
    if "enabled" in data:
        out["enabled"] = bool_field(data, "enabled")
    if "isDefault" in data:
        out["is_default"] = bool_field(data, "isDefault")
    if "config" in data:
        config = require_object(data["config"], "config")
        ensure_no_secret_like_keys(config)
        unknown = set(config) - PUBLIC_CONFIG_KEYS
        if unknown:
            raise APIError("validation_failed", "Provider config contains unsupported keys.", 422)
        _validate_public_config(config)
        out["config"] = config
    if "apiKey" in data:
        if data["apiKey"] is not None and not isinstance(data["apiKey"], str):
            raise APIError("validation_failed", "apiKey must be a string or null.", 422)
        if isinstance(data["apiKey"], str) and data["apiKey"].strip():
            data["apiKey"] = string_field(data, "apiKey", min_len=1, max_len=4096)
    return out


def _validate_public_config(config: dict):
    for key in {"reply", "transcript", "voice", "voiceId", "language", "responsePath", "textPath"} & set(config):
        if not isinstance(config[key], str) or len(config[key]) > 2000:
            raise APIError("validation_failed", f"config.{key} must be a bounded string.", 422)
    if "speed" in config:
        if not isinstance(config["speed"], (int, float)) or isinstance(config["speed"], bool):
            raise APIError("validation_failed", "config.speed must be a number.", 422)
        if float(config["speed"]) < 0.5 or float(config["speed"]) > 2.0:
            raise APIError("validation_failed", "config.speed is out of range.", 422)
        config["speed"] = float(config["speed"])
    if "fail" in config and not isinstance(config["fail"], bool):
        raise APIError("validation_failed", "config.fail must be a boolean.", 422)


def create_provider(user_id, data):
    attrs = validate_payload(data)
    provider = Provider(user_id=user_id, **attrs)
    db.session.add(provider)
    db.session.flush()
    if data.get("apiKey"):
        provider.credential = ProviderCredential(encrypted_api_key=encrypt_secret(data["apiKey"]), masked_hint=mask_secret(data["apiKey"]))
    if provider.is_default:
        _clear_other_defaults(provider)
    db.session.commit()
    return provider


def update_provider(provider_id, user_id, data):
    provider = _owned(provider_id, user_id)
    attrs = validate_payload(data, partial=True)
    for key, value in attrs.items():
        setattr(provider, key, value)
    if "apiKey" in data:
        if data["apiKey"]:
            if not provider.credential:
                provider.credential = ProviderCredential()
            provider.credential.encrypted_api_key = encrypt_secret(data["apiKey"])
            provider.credential.masked_hint = mask_secret(data["apiKey"])
        elif provider.credential:
            db.session.delete(provider.credential)
    if provider.is_default:
        _clear_other_defaults(provider)
    db.session.commit()
    return provider


def _clear_other_defaults(provider):
    Provider.query.filter(Provider.user_id == provider.user_id, Provider.kind == provider.kind, Provider.id != provider.id).update({"is_default": False})


def default_provider(user_id, kind):
    return Provider.query.filter_by(user_id=user_id, kind=kind, enabled=True, is_default=True).first() or Provider.query.filter_by(user_id=user_id, kind=kind, enabled=True).order_by(Provider.created_at.asc()).first()


def adapter_call(provider, method, *args):
    try:
        adapter = build(provider)
        return getattr(adapter, method)(*args)
    except ProviderFailure as exc:
        raise APIError(exc.code, exc.message, exc.status, exc.retryable) from None

from app.extensions import db
from app.models import Provider, ProviderCredential
from app.providers.base import ProviderFailure
from app.providers.registry import KINDS, build
from app.security.crypto import encrypt_secret, mask_secret
from app.security.errors import APIError

ADAPTERS = {"openai_compatible", "custom_http", "local_http", "mock"}


def _owned(provider_id, user_id):
    provider = db.session.get(Provider, provider_id)
    if not provider:
        raise APIError("not_found", "Provider was not found.", 404)
    if provider.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this provider.", 403)
    return provider


def validate_payload(data, partial=False):
    out = {}
    for field, attr in [("name", "name"), ("kind", "kind"), ("adapter", "adapter"), ("baseUrl", "base_url"), ("model", "model"), ("temperature", "temperature"), ("maxTokens", "max_tokens"), ("streaming", "streaming"), ("enabled", "enabled"), ("isDefault", "is_default"), ("config", "config")]:
        if field in data:
            out[attr] = data[field]
    if not partial:
        for required in ["name", "kind", "adapter"]:
            if required not in data or not data.get(required):
                raise APIError("validation_failed", f"{required} is required.", 422)
    if "kind" in out and out["kind"] not in KINDS:
        raise APIError("validation_failed", "Provider kind must be ai, stt or tts.", 422)
    if "adapter" in out and out["adapter"] not in ADAPTERS:
        raise APIError("validation_failed", "Provider adapter is not supported.", 422)
    if "name" in out:
        out["name"] = str(out["name"]).strip()[:120]
        if not out["name"]:
            raise APIError("validation_failed", "Provider name is required.", 422)
    if "config" in out and not isinstance(out["config"], dict):
        raise APIError("validation_failed", "Provider config must be an object.", 422)
    return out


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
        raise APIError(exc.code, exc.message, exc.status, exc.retryable)

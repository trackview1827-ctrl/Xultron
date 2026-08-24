from copy import deepcopy

from app.extensions import db
from app.models import DEFAULT_SETTINGS, UserSettings
from app.security.errors import APIError
from app.security.validation import bool_field, enum_field, require_object, string_field

THEMES = {"dark", "darker"}
ACCENTS = {"cyan", "violet"}
TEXT_SCALES = {"compact", "standard", "large"}
LOCALES = {"en", "tr", "es", "fr", "de"}
STT_LANGUAGES = {"auto", "en", "tr", "es", "fr", "de"}
BOOLEAN_SETTINGS = {
    "lowDataMode",
    "memoryEnabled",
    "conversationHistory",
    "voiceHistory",
    "saveAudio",
    "analytics",
    "reducedMotion",
}
STRING_SETTINGS = {"preferredVoice"}
ENUM_SETTINGS = {
    "locale": LOCALES,
    "sttLanguage": STT_LANGUAGES,
    "theme": THEMES,
    "accent": ACCENTS,
    "textScale": TEXT_SCALES,
}
ALLOWED_SETTINGS = set(DEFAULT_SETTINGS)


def _normalize_settings(values: dict) -> dict:
    merged = deepcopy(DEFAULT_SETTINGS)
    for key, value in (values or {}).items():
        if key in ALLOWED_SETTINGS:
            merged[key] = value
    if merged.get("analytics") is None:
        merged["analytics"] = False
    return merged


def get_settings(user):
    if not user.settings:
        user.settings = UserSettings(values=deepcopy(DEFAULT_SETTINGS))
        db.session.commit()
    user.settings.values = _normalize_settings(user.settings.values)
    return user.settings.to_public()


def _validate_patch(data: dict) -> dict:
    data = require_object(data)
    unknown = set(data) - ALLOWED_SETTINGS
    if unknown:
        raise APIError("validation_failed", "Unsupported setting key.", 422)
    patch = {}
    for key in BOOLEAN_SETTINGS:
        if key in data:
            patch[key] = bool_field(data, key)
    for key in STRING_SETTINGS:
        if key in data:
            patch[key] = string_field(data, key, max_len=120, default="") or ""
    for key, allowed in ENUM_SETTINGS.items():
        if key in data:
            patch[key] = enum_field(data, key, allowed, required=True)
    return patch


def patch_settings(user, data):
    if not user.settings:
        user.settings = UserSettings(values=deepcopy(DEFAULT_SETTINGS))
    merged = _normalize_settings(user.settings.to_public())
    merged.update(_validate_patch(data))
    user.settings.values = merged
    db.session.commit()
    return user.settings.to_public()

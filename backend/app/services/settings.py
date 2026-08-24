from copy import deepcopy

from app.extensions import db
from app.models import DEFAULT_SETTINGS, UserSettings


def get_settings(user):
    if not user.settings:
        user.settings = UserSettings()
        db.session.commit()
    return user.settings.to_public()


def patch_settings(user, data):
    allowed = set(DEFAULT_SETTINGS.keys())
    if not user.settings:
        user.settings = UserSettings()
    merged = deepcopy(user.settings.to_public())
    for key, value in data.items():
        if key in allowed:
            merged[key] = value
    if merged.get("analytics") is None:
        merged["analytics"] = False
    user.settings.values = merged
    db.session.commit()
    return user.settings.to_public()

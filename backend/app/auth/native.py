from flask import Blueprint, g, jsonify

from app.security.errors import APIError
from app.security.guards import require_json, require_mobile_principal
from app.services.device_auth import (
    audit_failure,
    enroll_mobile,
    guest_mobile,
    list_mobile_sessions,
    login_mobile,
    logout_mobile,
    refresh_mobile,
    revoke_mobile,
)

device_auth_bp = Blueprint("device_auth", __name__, url_prefix="/api/v1/device-auth")


def ok(payload=None, status=200):
    return jsonify(payload or {}), status


@device_auth_bp.post("/enroll")
def enroll():
    principal = g.get("mobile_principal")
    try:
        return ok(enroll_mobile(require_json(), principal), 201)
    except APIError as error:
        if error.code in {"identity_conflict", "invalid_credentials"}:
            audit_failure("enrollment_failed", error.code)
        raise


@device_auth_bp.post("/login")
def login():
    try:
        return ok(login_mobile(require_json()))
    except APIError as error:
        if error.code == "invalid_credentials":
            audit_failure("login_failed", error.code)
        raise


@device_auth_bp.post("/guest")
def guest():
    return ok(guest_mobile(require_json()), 201)


@device_auth_bp.post("/refresh")
def refresh():
    return ok(refresh_mobile(require_json()))


@device_auth_bp.post("/logout")
def logout():
    logout_mobile(require_json(), g.get("mobile_principal"))
    return ok({"ok": True})


@device_auth_bp.post("/revoke")
def revoke():
    revoke_mobile(require_json(), require_mobile_principal())
    return ok({"ok": True})


@device_auth_bp.get("/sessions")
def sessions():
    return ok({"sessions": list_mobile_sessions(require_mobile_principal())})

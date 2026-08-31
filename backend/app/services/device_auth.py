from datetime import timedelta

from flask import current_app, request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Device,
    MobileAccessToken,
    MobileAuthEvent,
    MobileAuthSession,
    MobileRefreshToken,
    User,
    UserSettings,
    utcnow,
)
from app.security.errors import APIError
from app.security.native_tokens import hash_opaque_token, new_opaque_token
from app.security.validation import require_object
from app.services.auth import authenticate_credentials, validate_registration


def _iso(value):
    return value.isoformat() + "Z"


def _audit(event_type, *, user=None, auth_session=None, device=None, details=None):
    db.session.add(
        MobileAuthEvent(
            user_id=user.id if user else None,
            session_id=auth_session.id if auth_session else None,
            device_id=device.id if device else None,
            event_type=event_type,
            ip_address=request.remote_addr,
            user_agent=(request.headers.get("User-Agent") or "")[:255],
            details=details or {},
        )
    )


def audit_failure(event_type, code):
    _audit(event_type, details={"reason": code})
    db.session.commit()


def _string(data, key, *, minimum=1, maximum=255, default=None):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise APIError("validation_failed", f"{key} must be a string.", 422)
    value = value.strip()
    if len(value) < minimum or len(value) > maximum:
        raise APIError("validation_failed", f"{key} is out of range.", 422)
    return value


def validate_device(data):
    data = require_object(data, "device")
    unexpected = sorted(set(data) - {"installationId", "name", "type", "appVersion", "metadata"})
    if unexpected:
        raise APIError("validation_failed", "Unexpected device fields are not allowed.", 422)

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise APIError("validation_failed", "metadata must be an object.", 422)
    metadata = dict(metadata)
    app_version = data.get("appVersion")
    if app_version is not None:
        if not isinstance(app_version, str) or not 1 <= len(app_version.strip()) <= 64:
            raise APIError("validation_failed", "appVersion is out of range.", 422)
        metadata["appVersion"] = app_version.strip()
    return {
        "installation_id": _string(data, "installationId", minimum=16, maximum=128),
        "name": _string(data, "name", maximum=120),
        "device_type": _string(data, "type", maximum=60, default="android"),
        "metadata": metadata,
    }


def register_device(user, data, *, expected_device=None, reactivate=False):
    values = validate_device(data)
    device = Device.query.filter_by(
        user_id=user.id, installation_id=values["installation_id"]
    ).first()
    if expected_device and (device is None or device.id != expected_device.id):
        raise APIError("device_mismatch", "The device identity does not match this session.", 409)
    if device is None:
        device = Device(
            user_id=user.id,
            installation_id=values["installation_id"],
            name=values["name"],
            device_type=values["device_type"],
            status="online",
            device_metadata=values["metadata"],
        )
        db.session.add(device)
        db.session.flush()
    else:
        device.name = values["name"]
        device.device_type = values["device_type"]
        device.status = "online"
        device.device_metadata = values["metadata"]
        device.last_seen_at = utcnow()
        if reactivate:
            device.revoked_at = None
        elif device.revoked_at:
            raise APIError("device_revoked", "The device has been revoked.", 401)
    return device


def _session_expiry(user):
    now = utcnow()
    expiry = now + timedelta(seconds=int(current_app.config["MOBILE_REFRESH_TOKEN_LIFETIME_SECONDS"]))
    if user.is_guest and user.guest_expires_at:
        expiry = min(expiry, user.guest_expires_at)
    return expiry


def _create_access_token(auth_session, now):
    plaintext = new_opaque_token("mat")
    expires_at = min(
        now + timedelta(seconds=int(current_app.config["MOBILE_ACCESS_TOKEN_LIFETIME_SECONDS"])),
        auth_session.expires_at,
    )
    db.session.add(
        MobileAccessToken(
            session_id=auth_session.id,
            token_hash=hash_opaque_token(plaintext),
            expires_at=expires_at,
        )
    )
    return plaintext, expires_at


def _create_refresh_token(auth_session, now, parent_id=None):
    plaintext = new_opaque_token("mrt")
    record = MobileRefreshToken(
        session_id=auth_session.id,
        parent_id=parent_id,
        token_hash=hash_opaque_token(plaintext),
        expires_at=auth_session.expires_at,
    )
    db.session.add(record)
    return plaintext, record


def _token_response(user, auth_session, access_token, access_expires_at, refresh_token):
    now = utcnow()
    return {
        "tokenType": "Bearer",
        "accessToken": access_token,
        "accessExpiresAt": _iso(access_expires_at),
        "expiresIn": max(0, int((access_expires_at - now).total_seconds())),
        "refreshToken": refresh_token,
        "refreshExpiresAt": _iso(auth_session.expires_at),
        "user": user.to_public(),
        "session": auth_session.to_public(auth_session.id),
    }


def _issue_session(user, device, event_type):
    now = utcnow()
    auth_session = MobileAuthSession(
        user_id=user.id,
        device_id=device.id,
        expires_at=_session_expiry(user),
    )
    db.session.add(auth_session)
    db.session.flush()
    access_token, access_expires_at = _create_access_token(auth_session, now)
    refresh_token, _ = _create_refresh_token(auth_session, now)
    _audit(event_type, user=user, auth_session=auth_session, device=device)
    db.session.commit()
    return _token_response(user, auth_session, access_token, access_expires_at, refresh_token)


def login_mobile(data):
    data = require_object(data)
    unexpected = sorted(set(data) - {"identifier", "password", "device"})
    if unexpected:
        raise APIError("validation_failed", "Unexpected login fields are not allowed.", 422)
    user = authenticate_credentials(data)
    device = register_device(user, data.get("device"), reactivate=True)
    return _issue_session(user, device, "login_succeeded")


def enroll_mobile(data, current_principal=None):
    data = require_object(data)
    unexpected = sorted(set(data) - {"username", "email", "password", "device"})
    if unexpected:
        raise APIError("validation_failed", "Unexpected enrollment fields are not allowed.", 422)
    username, email, password = validate_registration(data)
    current_user = current_principal.user if current_principal else None
    if current_user and not current_user.is_guest:
        raise APIError("identity_conflict", "This mobile session is already registered.", 409)
    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing and (current_user is None or existing.id != current_user.id):
        raise APIError("identity_conflict", "Username or email is already in use.", 409)

    if current_user:
        user = current_user
        user.username = username
        user.email = email
        user.is_guest = False
        user.guest_expires_at = None
        revoke_session(current_principal.auth_session, "guest_upgraded")
    else:
        user = User(username=username, email=email, is_guest=False)
        user.settings = UserSettings()
        db.session.add(user)
    user.set_password(password)
    try:
        db.session.flush()
        device = register_device(user, data.get("device"), reactivate=True)
        return _issue_session(user, device, "enrollment_succeeded")
    except IntegrityError:
        db.session.rollback()
        raise APIError("identity_conflict", "Username or email is already in use.", 409)


def guest_mobile(data):
    data = require_object(data)
    unexpected = sorted(set(data) - {"device"})
    if unexpected:
        raise APIError("validation_failed", "Unexpected guest fields are not allowed.", 422)
    import secrets

    user = User(
        username=f"guest_{secrets.token_hex(8)}",
        is_guest=True,
        guest_expires_at=utcnow() + timedelta(seconds=current_app.config["GUEST_LIFETIME_SECONDS"]),
    )
    user.settings = UserSettings()
    db.session.add(user)
    db.session.flush()
    device = register_device(user, data.get("device"), reactivate=True)
    return _issue_session(user, device, "guest_created")


def revoke_session(auth_session, reason):
    if auth_session.revoked_at:
        return
    now = utcnow()
    auth_session.revoked_at = now
    auth_session.revoke_reason = reason
    MobileAccessToken.query.filter_by(session_id=auth_session.id).filter(
        MobileAccessToken.revoked_at.is_(None)
    ).update({"revoked_at": now}, synchronize_session=False)
    MobileRefreshToken.query.filter_by(session_id=auth_session.id).filter(
        MobileRefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": now}, synchronize_session=False)


def _valid_refresh_value(data):
    data = require_object(data)
    unexpected = sorted(set(data) - {"refreshToken"})
    if unexpected:
        raise APIError("validation_failed", "Unexpected refresh fields are not allowed.", 422)
    token = data.get("refreshToken")
    if not isinstance(token, str) or not token.startswith("mrt_") or len(token) > 512:
        raise APIError("invalid_refresh_token", "The refresh token is invalid.", 401)
    return token


def refresh_mobile(data):
    plaintext = _valid_refresh_value(data)
    token_hash = hash_opaque_token(plaintext)
    record = MobileRefreshToken.query.filter_by(token_hash=token_hash).first()
    if record is None:
        raise APIError("invalid_refresh_token", "The refresh token is invalid.", 401)

    now = utcnow()
    auth_session = record.auth_session
    if record.consumed_at and not auth_session.revoked_at:
        revoke_session(auth_session, "refresh_reuse")
        _audit(
            "refresh_reuse_detected",
            user=auth_session.user,
            auth_session=auth_session,
            device=auth_session.device,
        )
        current_app.logger.warning(
            "Mobile refresh token reuse detected session_id=%s device_id=%s",
            auth_session.id,
            auth_session.device_id,
        )
        db.session.commit()
        raise APIError(
            "refresh_reuse_detected",
            "Refresh token reuse was detected and the token family was revoked.",
            401,
        )
    if record.revoked_at or auth_session.revoked_at or auth_session.device.revoked_at:
        raise APIError("refresh_token_revoked", "The refresh token has been revoked.", 401)
    if record.expires_at <= now or auth_session.expires_at <= now:
        raise APIError("refresh_token_expired", "The refresh token has expired.", 401)
    user = auth_session.user
    if user.is_guest and (not user.guest_expires_at or user.guest_expires_at <= now):
        raise APIError("guest_expired", "The guest session has expired.", 401)

    result = db.session.execute(
        update(MobileRefreshToken)
        .where(
            MobileRefreshToken.id == record.id,
            MobileRefreshToken.consumed_at.is_(None),
            MobileRefreshToken.revoked_at.is_(None),
        )
        .values(consumed_at=now)
    )
    if result.rowcount != 1:
        db.session.rollback()
        current = db.session.get(MobileRefreshToken, record.id)
        if current and current.consumed_at and not current.auth_session.revoked_at:
            revoke_session(current.auth_session, "refresh_reuse")
            _audit(
                "refresh_reuse_detected",
                user=current.auth_session.user,
                auth_session=current.auth_session,
                device=current.auth_session.device,
            )
            db.session.commit()
            raise APIError(
                "refresh_reuse_detected",
                "Refresh token reuse was detected and the token family was revoked.",
                401,
            )
        raise APIError("refresh_token_revoked", "The refresh token has been revoked.", 401)

    auth_session.last_seen_at = now
    auth_session.device.last_seen_at = now
    access_token, access_expires_at = _create_access_token(auth_session, now)
    refresh_token, _ = _create_refresh_token(auth_session, now, parent_id=record.id)
    _audit(
        "refresh_rotated",
        user=user,
        auth_session=auth_session,
        device=auth_session.device,
    )
    db.session.commit()
    return _token_response(user, auth_session, access_token, access_expires_at, refresh_token)


def logout_mobile(data, principal=None):
    auth_session = principal.auth_session if principal else None
    if auth_session is None:
        try:
            plaintext = _valid_refresh_value(data)
        except APIError as error:
            if error.code == "invalid_refresh_token":
                return
            raise
        record = MobileRefreshToken.query.filter_by(
            token_hash=hash_opaque_token(plaintext)
        ).first()
        auth_session = record.auth_session if record else None
    if auth_session:
        revoke_session(auth_session, "logout")
        _audit(
            "logout",
            user=auth_session.user,
            auth_session=auth_session,
            device=auth_session.device,
        )
        db.session.commit()


def revoke_mobile(data, principal):
    data = require_object(data)
    unexpected = sorted(set(data) - {"sessionId", "deviceId"})
    if unexpected:
        raise APIError("validation_failed", "Unexpected revoke fields are not allowed.", 422)
    session_id = data.get("sessionId")
    device_id = data.get("deviceId")
    if bool(session_id) == bool(device_id):
        raise APIError("validation_failed", "Provide exactly one of sessionId or deviceId.", 422)

    if session_id:
        if not isinstance(session_id, str) or len(session_id) > 40:
            raise APIError("validation_failed", "sessionId is invalid.", 422)
        target = db.session.get(MobileAuthSession, session_id)
        if target is None:
            raise APIError("not_found", "Mobile session was not found.", 404)
        if target.user_id != principal.user.id:
            raise APIError("forbidden", "You do not have access to this mobile session.", 403)
        revoke_session(target, "user_revoked")
        _audit("session_revoked", user=principal.user, auth_session=target, device=target.device)
    else:
        if not isinstance(device_id, str) or len(device_id) > 40:
            raise APIError("validation_failed", "deviceId is invalid.", 422)
        device = db.session.get(Device, device_id)
        if device is None:
            raise APIError("not_found", "Device was not found.", 404)
        if device.user_id != principal.user.id:
            raise APIError("forbidden", "You do not have access to this device.", 403)
        device.revoked_at = utcnow()
        device.status = "offline"
        sessions = MobileAuthSession.query.filter_by(user_id=principal.user.id, device_id=device.id).all()
        for target in sessions:
            revoke_session(target, "device_revoked")
        _audit("device_revoked", user=principal.user, device=device)
    db.session.commit()


def list_mobile_sessions(principal):
    rows = (
        MobileAuthSession.query.filter_by(user_id=principal.user.id)
        .order_by(MobileAuthSession.created_at.desc())
        .all()
    )
    return [row.to_public(principal.auth_session.id) for row in rows]


def register_current_device(data, principal):
    device = register_device(
        principal.user,
        data,
        expected_device=principal.device,
        reactivate=False,
    )
    device.last_seen_at = utcnow()
    _audit(
        "device_registered",
        user=principal.user,
        auth_session=principal.auth_session,
        device=device,
    )
    db.session.commit()
    return device

import hashlib
import secrets
from dataclasses import dataclass

from flask import request

from app.models import MobileAccessToken, MobileAuthSession, User, utcnow
from app.security.errors import APIError


@dataclass(frozen=True)
class MobilePrincipal:
    access_token: MobileAccessToken
    auth_session: MobileAuthSession
    user: User

    @property
    def device(self):
        return self.auth_session.device


def new_opaque_token(prefix: str) -> str:
    """Return a high-entropy bearer credential. Only its SHA-256 digest is persisted."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_bearer_header(value: str) -> str:
    parts = value.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise APIError("invalid_access_token", "The access token is invalid.", 401)
    token = parts[1]
    if not token.startswith("mat_") or len(token) > 512:
        raise APIError("invalid_access_token", "The access token is invalid.", 401)
    return token


def authenticate_bearer_header(value: str) -> MobilePrincipal:
    token = parse_bearer_header(value)
    record = MobileAccessToken.query.filter_by(token_hash=hash_opaque_token(token)).first()
    if record is None:
        raise APIError("invalid_access_token", "The access token is invalid.", 401)

    now = utcnow()
    auth_session = record.auth_session
    if record.expires_at <= now:
        raise APIError("access_token_expired", "The access token has expired.", 401)
    if record.revoked_at or auth_session.revoked_at or auth_session.device.revoked_at:
        raise APIError("access_token_revoked", "The access token has been revoked.", 401)
    if auth_session.expires_at <= now:
        raise APIError("mobile_session_expired", "The mobile session has expired.", 401)

    supplied_device_id = request.headers.get("X-Device-ID")
    if not supplied_device_id:
        raise APIError("device_header_required", "The mobile device identity header is required.", 401)
    if supplied_device_id != auth_session.device_id:
        raise APIError("device_mismatch", "The access token is bound to another device.", 401)

    user = auth_session.user
    if user.is_guest and (not user.guest_expires_at or user.guest_expires_at <= now):
        raise APIError("guest_expired", "The guest session has expired.", 401)
    return MobilePrincipal(record, auth_session, user)

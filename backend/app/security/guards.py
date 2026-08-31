import hashlib
import hmac
import re
import threading
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from flask import current_app, g, request, session

from app.extensions import db
from app.models import Session
from app.security.errors import APIError

_hits = {}
_hits_lock = threading.Lock()
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def install_guards(app):
    @app.before_request
    def assign_request_id_and_session():
        supplied_request_id = request.headers.get("X-Request-ID")
        if supplied_request_id and not REQUEST_ID_RE.fullmatch(supplied_request_id):
            raise APIError("validation_failed", "X-Request-ID is invalid.", 422)
        request.request_id = supplied_request_id or f"req_{uuid.uuid4().hex}"
        g.current_user = None
        g.current_session = None
        g.mobile_principal = None
        g.current_mobile_session = None
        g.current_device = None
        g.auth_method = None
        authorization = request.headers.get("Authorization")
        if authorization:
            from app.security.native_tokens import authenticate_bearer_header

            principal = authenticate_bearer_header(authorization)
            g.mobile_principal = principal
            g.current_mobile_session = principal.auth_session
            g.current_device = principal.device
            g.current_user = principal.user
            g.auth_method = "mobile_bearer"
            return
        sid = session.get("sid")
        if sid:
            rec = db.session.get(Session, sid)
            csrf_token = session.get("csrf_token")
            valid_csrf = bool(rec and csrf_token and hmac.compare_digest(hashlib.sha256(csrf_token.encode()).hexdigest(), rec.csrf_token_hash))
            if rec and not rec.revoked_at and rec.expires_at > utcnow() and valid_csrf:
                g.current_session = rec
                g.current_user = rec.user
                g.auth_method = "web_cookie"
                rec.last_seen_at = utcnow()
            else:
                session.pop("sid", None)

    @app.before_request
    def same_origin_csrf_rate_limit():
        if not request.path.startswith("/api/v1"):
            return None
        _rate_limit()
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            if g.get("auth_method") == "mobile_bearer" or request.path.startswith(
                "/api/v1/device-auth/"
            ):
                return None
            _enforce_same_origin()
            expected = session.get("csrf_token")
            supplied = request.headers.get("X-CSRF-Token")
            if not expected or not supplied or not hmac.compare_digest(supplied, expected):
                raise APIError("csrf_failed", "CSRF validation failed.", 403)
        return None

    @app.after_request
    def secure_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=(), payment=(), usb=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' data: blob:; connect-src 'self'; "
            "font-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        )
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if not response.headers.get("Cache-Control"):
            response.headers["Cache-Control"] = "no-store"
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response


def _rate_limit():
    if request.endpoint == "api_v1.auth_login" or request.path.startswith(
        "/api/v1/device-auth/"
    ):
        limit = int(current_app.config.get("AUTH_RATE_LIMIT_PER_MINUTE", 10))
    else:
        limit = int(current_app.config.get("RATE_LIMIT_PER_MINUTE", 120))
    if limit <= 0:
        return
    now = time.time()
    bucket = int(now // 60)
    key = (request.remote_addr or "local", getattr(g.current_user, "id", "anon"), request.endpoint or request.path, bucket)
    with _hits_lock:
        _hits[key] = _hits.get(key, 0) + 1
        exceeded = _hits[key] > limit
        if len(_hits) > 20000:
            old = bucket - 2
            for k in list(_hits):
                if k[-1] < old:
                    _hits.pop(k, None)
    if exceeded:
        raise APIError("rate_limited", "Too many requests. Please slow down.", 429, retryable=True)


def _enforce_same_origin():
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        return
    parsed = urlparse(origin)
    supplied = f"{parsed.scheme}://{parsed.netloc}"
    expected = request.host_url.rstrip("/")
    allowed = set(current_app.config.get("ALLOWED_ORIGINS") or []) | {expected}
    if supplied not in allowed:
        raise APIError("same_origin_required", "Cross-origin requests are not allowed.", 403)


def require_user():
    if not g.get("current_user"):
        raise APIError("authentication_required", "Authentication is required.", 401)
    return g.current_user


def require_mobile_principal():
    principal = g.get("mobile_principal")
    if not principal:
        raise APIError("mobile_authentication_required", "Mobile bearer authentication is required.", 401)
    return principal


def require_json():
    if not request.is_json:
        raise APIError("invalid_json", "A JSON body is required.", 400)
    data = request.get_json(silent=True)
    if data is None:
        raise APIError("invalid_json", "A valid JSON body is required.", 400)
    if not isinstance(data, dict):
        raise APIError("validation_failed", "JSON body must be an object.", 422)
    return data

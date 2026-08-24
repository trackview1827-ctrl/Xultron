import hashlib
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from flask import current_app, g, request, session

from app.extensions import db
from app.models import Session
from app.security.errors import APIError

_hits = {}


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def install_guards(app):
    @app.before_request
    def assign_request_id_and_session():
        request.request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        g.current_user = None
        g.current_session = None
        sid = session.get("sid")
        if sid:
            rec = db.session.get(Session, sid)
            csrf_token = session.get("csrf_token")
            valid_csrf = bool(rec and csrf_token and hashlib.sha256(csrf_token.encode()).hexdigest() == rec.csrf_token_hash)
            if rec and not rec.revoked_at and rec.expires_at > utcnow() and valid_csrf:
                g.current_session = rec
                g.current_user = rec.user
                rec.last_seen_at = utcnow()
            else:
                session.pop("sid", None)

    @app.before_request
    def same_origin_csrf_rate_limit():
        if not request.path.startswith("/api/v1"):
            return None
        _rate_limit()
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            _enforce_same_origin()
            expected = session.get("csrf_token")
            supplied = request.headers.get("X-CSRF-Token")
            if not expected or not supplied or supplied != expected:
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
    limit = int(current_app.config.get("RATE_LIMIT_PER_MINUTE", 120))
    if limit <= 0:
        return
    now = time.time()
    bucket = int(now // 60)
    key = (request.remote_addr or "local", getattr(g.current_user, "id", "anon"), request.endpoint or request.path, bucket)
    _hits[key] = _hits.get(key, 0) + 1
    if _hits[key] > limit:
        raise APIError("rate_limited", "Too many requests. Please slow down.", 429, retryable=True)
    if len(_hits) > 20000:
        old = bucket - 2
        for k in list(_hits):
            if k[-1] < old:
                _hits.pop(k, None)


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


def require_json():
    if not request.is_json:
        raise APIError("invalid_json", "A JSON body is required.", 400)
    data = request.get_json(silent=True)
    if data is None:
        raise APIError("invalid_json", "A valid JSON body is required.", 400)
    if not isinstance(data, dict):
        raise APIError("validation_failed", "JSON body must be an object.", 422)
    return data

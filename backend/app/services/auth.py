import hashlib
import secrets
from datetime import timedelta

from flask import current_app, request, session
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Session, User, UserSettings, utcnow
from app.security.errors import APIError
from app.security.validation import normalize_email, normalize_username, require_object


def ensure_csrf() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def rotate_csrf() -> str:
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _create_session(user: User, guest: bool = False) -> Session:
    if not session.get("csrf_token"):
        rotate_csrf()
    lifetime = current_app.config["GUEST_LIFETIME_SECONDS"] if guest else current_app.config["PERMANENT_SESSION_LIFETIME_SECONDS"]
    expires = utcnow() + timedelta(seconds=lifetime)
    rec = Session(
        user=user,
        csrf_token_hash=hash_token(session["csrf_token"]),
        user_agent=(request.headers.get("User-Agent") or "")[:255],
        ip_address=request.remote_addr,
        expires_at=expires,
    )
    db.session.add(rec)
    db.session.flush()
    session["sid"] = rec.id
    session.permanent = True
    return rec


def create_guest():
    from flask import g
    if g.get("current_user") and g.current_user.is_guest:
        return g.current_user, g.current_session
    if g.get("current_user") and not g.current_user.is_guest:
        raise APIError("identity_conflict", "Sign out before starting a guest session.", 409)
    rotate_csrf()
    user = User(username=f"guest_{secrets.token_hex(8)}", is_guest=True, guest_expires_at=utcnow() + timedelta(seconds=current_app.config["GUEST_LIFETIME_SECONDS"]))
    user.settings = UserSettings()
    db.session.add(user)
    db.session.flush()
    rec = _create_session(user, guest=True)
    db.session.commit()
    return user, rec


def validate_registration(data):
    data = require_object(data)
    username = normalize_username(data.get("username"))
    email = normalize_email(data.get("email"))
    password = data.get("password")
    if not isinstance(password, str):
        raise APIError("validation_failed", "password must be a string.", 422)
    if len(password) < 10:
        raise APIError("validation_failed", "Password must be at least 10 characters.", 422)
    if len(password) > 1024:
        raise APIError("validation_failed", "password is too long.", 422)
    return username, email, password


def register(data):
    from flask import g
    username, email, password = validate_registration(data)
    current = g.get("current_user")
    if current and not current.is_guest:
        raise APIError("identity_conflict", "You are already registered. Sign out before creating another account.", 409)
    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing and not (current and existing.id == current.id and existing.is_guest):
        raise APIError("identity_conflict", "Username or email is already in use.", 409)
    if current and current.is_guest:
        user = current
        user.username = username
        user.email = email
        user.is_guest = False
        user.guest_expires_at = None
    else:
        user = User(username=username, email=email, is_guest=False)
        user.settings = UserSettings()
        db.session.add(user)
    user.set_password(password)
    if g.get("current_session"):
        g.current_session.revoked_at = utcnow()
        session.pop("sid", None)
    rotate_csrf()
    _create_session(user, guest=False)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise APIError("identity_conflict", "Username or email is already in use.", 409)
    return user


def login(data):
    data = require_object(data)
    if not isinstance(data.get("identifier"), str) or not isinstance(data.get("password"), str):
        raise APIError("validation_failed", "Identifier and password must be strings.", 422)
    identifier = data.get("identifier", "").strip().lower()
    password = data.get("password", "")
    if not identifier or not password:
        raise APIError("invalid_credentials", "Identifier and password are required.", 401)
    if len(identifier) > 255 or len(password) > 1024:
        raise APIError("validation_failed", "Identifier or password is too long.", 422)
    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
    if not user or user.is_guest or not user.check_password(password):
        raise APIError("invalid_credentials", "Invalid identifier or password.", 401)
    from flask import g
    if g.get("current_session"):
        g.current_session.revoked_at = utcnow()
        session.pop("sid", None)
    rotate_csrf()
    _create_session(user, guest=False)
    db.session.commit()
    return user


def logout():
    from flask import g
    if g.get("current_session"):
        g.current_session.revoked_at = utcnow()
        db.session.commit()
    session.clear()


def cleanup_expired():
    now = utcnow()
    expired_sessions = Session.query.filter((Session.expires_at <= now) | (Session.revoked_at.isnot(None))).delete(synchronize_session=False)
    guests = User.query.filter(User.is_guest.is_(True), User.guest_expires_at <= now).all()
    guest_count = len(guests)
    for user in guests:
        db.session.delete(user)
    db.session.commit()
    return {"expiredSessions": expired_sessions, "expiredGuests": guest_count}

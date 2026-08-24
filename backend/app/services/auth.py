import hashlib
import secrets
from datetime import timedelta

from flask import current_app, request, session

from app.extensions import db
from app.models import Session, User, UserSettings, utcnow
from app.security.errors import APIError


def ensure_csrf() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _create_session(user: User, guest: bool = False) -> Session:
    ensure_csrf()
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
    user = User(username=f"guest_{secrets.token_hex(8)}", is_guest=True, guest_expires_at=utcnow() + timedelta(seconds=current_app.config["GUEST_LIFETIME_SECONDS"]))
    user.settings = UserSettings()
    db.session.add(user)
    db.session.flush()
    rec = _create_session(user, guest=True)
    db.session.commit()
    return user, rec


def validate_registration(data):
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not username or not email or not password:
        raise APIError("validation_failed", "Username, email and password are required.", 422)
    if len(password) < 8:
        raise APIError("validation_failed", "Password must be at least 8 characters.", 422)
    return username, email, password


def register(data):
    from flask import g
    username, email, password = validate_registration(data)
    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing and not (g.get("current_user") and existing.id == g.current_user.id and existing.is_guest):
        raise APIError("identity_conflict", "Username or email is already in use.", 409)
    if g.get("current_user") and g.current_user.is_guest:
        user = g.current_user
        user.username = username
        user.email = email
        user.is_guest = False
        user.guest_expires_at = None
    else:
        user = User(username=username, email=email, is_guest=False)
        user.settings = UserSettings()
        db.session.add(user)
    user.set_password(password)
    if not g.get("current_session"):
        _create_session(user, guest=False)
    else:
        g.current_session.expires_at = utcnow() + timedelta(seconds=current_app.config["PERMANENT_SESSION_LIFETIME_SECONDS"])
    db.session.commit()
    return user


def login(data):
    identifier = (data.get("identifier") or "").strip().lower()
    password = data.get("password") or ""
    if not identifier or not password:
        raise APIError("invalid_credentials", "Identifier and password are required.", 401)
    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
    if not user or user.is_guest or not user.check_password(password):
        raise APIError("invalid_credentials", "Invalid identifier or password.", 401)
    from flask import g
    if g.get("current_session"):
        g.current_session.revoked_at = utcnow()
    _create_session(user, guest=False)
    db.session.commit()
    return user


def logout():
    from flask import g
    if g.get("current_session"):
        g.current_session.revoked_at = utcnow()
        db.session.commit()
    session.pop("sid", None)


def cleanup_expired():
    now = utcnow()
    expired_sessions = Session.query.filter((Session.expires_at <= now) | (Session.revoked_at.isnot(None))).delete(synchronize_session=False)
    guests = User.query.filter(User.is_guest.is_(True), User.guest_expires_at <= now).all()
    guest_count = len(guests)
    for user in guests:
        db.session.delete(user)
    db.session.commit()
    return {"expiredSessions": expired_sessions, "expiredGuests": guest_count}

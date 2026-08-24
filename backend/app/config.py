import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_SECRETS = INSTANCE_DIR / "secrets.env"


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _load_instance_secrets(env: str) -> dict[str, str]:
    """Load or create ignored per-install secrets for non-production runs.

    The repo ignores instance/, so development gets persistent random secrets without
    checking them into source. Production never auto-generates secrets and therefore
    fails closed when deployment env vars are missing.
    """
    if env == "production":
        return {}
    values: dict[str, str] = {}
    if INSTANCE_SECRETS.exists():
        for line in INSTANCE_SECRETS.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    changed = False
    if not values.get("SECRET_KEY"):
        values["SECRET_KEY"] = secrets.token_urlsafe(48)
        changed = True
    if not values.get("ENCRYPTION_KEY"):
        values["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        changed = True
    if changed:
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        INSTANCE_SECRETS.write_text(
            "# Ignored local Xultron backend secrets. Do not commit.\n"
            f"SECRET_KEY={values['SECRET_KEY']}\n"
            f"ENCRYPTION_KEY={values['ENCRYPTION_KEY']}\n"
        )
        try:
            INSTANCE_SECRETS.chmod(0o600)
        except OSError:
            pass
    return values


_ENV = os.getenv("XULTRON_ENV", "development")
_INSTANCE = _load_instance_secrets(_ENV)

# This local-only identity is intentionally disabled by default in production.
# The default stores only a one-way scrypt hash, never the requested PIN itself.
_DEFAULT_LOCAL_PIN_HASH = (
    "scrypt:32768:8:1$example$"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)


class Config:
    XULTRON_ENV = _ENV
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY") or _INSTANCE.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'instance' / 'xultron.sqlite3'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_NAME = "xultron_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", XULTRON_ENV == "production")
    PERMANENT_SESSION_LIFETIME_SECONDS = int(os.getenv("SESSION_LIFETIME_SECONDS", "2592000"))
    GUEST_LIFETIME_SECONDS = int(os.getenv("GUEST_LIFETIME_SECONDS", "86400"))
    MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", "5242880"))
    MAX_CONTENT_LENGTH = max(int(os.getenv("MAX_CONTENT_LENGTH", "6291456")), MAX_AUDIO_BYTES + 1048576)
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    AUTH_RATE_LIMIT_PER_MINUTE = int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "10"))
    PROVIDER_TIMEOUT_SECONDS = int(os.getenv("PROVIDER_TIMEOUT_SECONDS", "20"))
    MAX_PROVIDER_RESPONSE_BYTES = int(os.getenv("MAX_PROVIDER_RESPONSE_BYTES", "1048576"))
    MAX_PROVIDER_TEXT_CHARS = int(os.getenv("MAX_PROVIDER_TEXT_CHARS", "24000"))
    WTF_CSRF_ENABLED = False
    JSON_SORT_KEYS = False
    ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY") or _INSTANCE.get("ENCRYPTION_KEY")
    FRONTEND_DIST_DIR = os.getenv("FRONTEND_DIST_DIR") or str(BASE_DIR.parent / "frontend" / "dist")
    LOCAL_PIN_LOGIN_ENABLED = _bool("LOCAL_PIN_LOGIN_ENABLED", XULTRON_ENV != "production")
    LOCAL_PIN_USERNAME = (os.getenv("LOCAL_PIN_USERNAME") or "local-user").strip().lower()
    LOCAL_PIN_HASH = os.getenv("LOCAL_PIN_HASH") or _DEFAULT_LOCAL_PIN_HASH

    @classmethod
    def validate(cls):
        if cls.XULTRON_ENV == "production":
            if not cls.SECRET_KEY:
                raise RuntimeError("SECRET_KEY is required in production")
            if not cls.ENCRYPTION_KEY:
                raise RuntimeError("ENCRYPTION_KEY is required in production")
        if not cls.SECRET_KEY:
            raise RuntimeError("SECRET_KEY is required")
        if not cls.ENCRYPTION_KEY:
            raise RuntimeError("ENCRYPTION_KEY is required")
        if cls.ENCRYPTION_KEY:
            Fernet(cls.ENCRYPTION_KEY.encode() if isinstance(cls.ENCRYPTION_KEY, str) else cls.ENCRYPTION_KEY)
        if cls.LOCAL_PIN_LOGIN_ENABLED:
            if not cls.LOCAL_PIN_USERNAME:
                raise RuntimeError("LOCAL_PIN_USERNAME is required when local PIN login is enabled")
            if not cls.LOCAL_PIN_HASH:
                raise RuntimeError("LOCAL_PIN_HASH is required when local PIN login is enabled")


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    RATE_LIMIT_PER_MINUTE = 1000
    AUTH_RATE_LIMIT_PER_MINUTE = 1000
    SERVER_NAME = "localhost"
    SESSION_COOKIE_SECURE = False

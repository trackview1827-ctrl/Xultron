import os
from pathlib import Path

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


class Config:
    XULTRON_ENV = os.getenv("XULTRON_ENV", "development")
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-only-change-me" if XULTRON_ENV != "production" else None)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'instance' / 'xultron.sqlite3'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_NAME = "xultron_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", XULTRON_ENV == "production")
    PERMANENT_SESSION_LIFETIME_SECONDS = int(os.getenv("SESSION_LIFETIME_SECONDS", "2592000"))
    GUEST_LIFETIME_SECONDS = int(os.getenv("GUEST_LIFETIME_SECONDS", "86400"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "1048576"))
    MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", "5242880"))
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    PROVIDER_TIMEOUT_SECONDS = int(os.getenv("PROVIDER_TIMEOUT_SECONDS", "20"))
    WTF_CSRF_ENABLED = False
    JSON_SORT_KEYS = False
    ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

    @classmethod
    def validate(cls):
        if cls.XULTRON_ENV == "production":
            if not cls.SECRET_KEY:
                raise RuntimeError("SECRET_KEY is required in production")
            if not cls.ENCRYPTION_KEY:
                raise RuntimeError("ENCRYPTION_KEY is required in production")
        if cls.ENCRYPTION_KEY:
            Fernet(cls.ENCRYPTION_KEY.encode() if isinstance(cls.ENCRYPTION_KEY, str) else cls.ENCRYPTION_KEY)


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    RATE_LIMIT_PER_MINUTE = 1000
    SERVER_NAME = "localhost"
    SESSION_COOKIE_SECURE = False

import base64
import hashlib
from cryptography.fernet import Fernet
from flask import current_app


def _dev_key(secret_key: str) -> bytes:
    digest = hashlib.sha256((secret_key + ":xultron-fernet").encode()).digest()
    return base64.urlsafe_b64encode(digest)


def fernet() -> Fernet:
    key = current_app.config.get("ENCRYPTION_KEY")
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)
    return Fernet(_dev_key(current_app.config["SECRET_KEY"]))


def encrypt_secret(value: str | None) -> bytes | None:
    if not value:
        return None
    return fernet().encrypt(value.encode())


def decrypt_secret(value: bytes | None) -> str | None:
    if not value:
        return None
    return fernet().decrypt(value).decode()


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "••••"
    return f"{value[:3]}••••••••{value[-4:]}"

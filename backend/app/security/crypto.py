from cryptography.fernet import Fernet
from flask import current_app


def fernet() -> Fernet:
    key = current_app.config.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is required")
    return Fernet(key.encode() if isinstance(key, str) else key)


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

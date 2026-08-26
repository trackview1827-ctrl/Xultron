import uuid
from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("usr"))
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=True, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    is_guest = db.Column(db.Boolean, default=False, nullable=False, index=True)
    guest_expires_at = db.Column(db.DateTime, nullable=True, index=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return bool(self.password_hash and check_password_hash(self.password_hash, password))

    def to_public(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "isGuest": self.is_guest,
            "createdAt": self.created_at.isoformat() + "Z",
        }


class Session(db.Model):
    __tablename__ = "sessions"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("ses"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    csrf_token_hash = db.Column(db.String(128), nullable=False)
    user_agent = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_seen_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)

    user = relationship("User", back_populates="sessions")

    def to_public(self, current_id=None):
        return {
            "id": self.id,
            "createdAt": self.created_at.isoformat() + "Z",
            "lastSeenAt": self.last_seen_at.isoformat() + "Z",
            "expiresAt": self.expires_at.isoformat() + "Z",
            "current": self.id == current_id,
        }


class Conversation(TimestampMixin, db.Model):
    __tablename__ = "conversations"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("con"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False, default="New conversation")
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def to_public(self):
        return {
            "id": self.id,
            "title": self.title,
            "createdAt": self.created_at.isoformat() + "Z",
            "updatedAt": self.updated_at.isoformat() + "Z",
        }


class Message(TimestampMixin, db.Model):
    __tablename__ = "messages"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("msg"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = db.Column(db.String(40), db.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    request_id = db.Column(db.String(100), nullable=True, index=True)
    provider_id = db.Column(db.String(40), nullable=True)
    meta = db.Column(db.JSON, default=dict, nullable=False)
    conversation = relationship("Conversation", back_populates="messages")

    def to_public(self):
        return {
            "id": self.id,
            "conversationId": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "createdAt": self.created_at.isoformat() + "Z",
            "requestId": self.request_id,
        }


class Task(TimestampMixin, db.Model):
    """Durable unit of agent work and its observable lifecycle state."""
    __tablename__ = "tasks"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("tsk"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    instruction = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    result = db.Column(db.JSON, nullable=True)
    error = db.Column(db.String(1000), nullable=True)
    worker_id = db.Column(db.String(120), nullable=True, index=True)
    lease_expires_at = db.Column(db.DateTime, nullable=True, index=True)

    def to_public(self):
        return {"id": self.id, "title": self.title, "instruction": self.instruction,
                "status": self.status, "result": self.result, "error": self.error,
                "workerId": self.worker_id,
                "leaseExpiresAt": self.lease_expires_at.isoformat() + "Z" if self.lease_expires_at else None,
                "createdAt": self.created_at.isoformat() + "Z", "updatedAt": self.updated_at.isoformat() + "Z"}


class IdempotencyKey(db.Model):
    __tablename__ = "idempotency_keys"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("idem"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_id = db.Column(db.String(100), nullable=False)
    request_fingerprint = db.Column(db.String(64), nullable=True)
    response = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_idempotency_user_request"),)


class MemoryItem(TimestampMixin, db.Model):
    __tablename__ = "memory_items"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("mem"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(40), nullable=False, default="personal", index=True)

    def to_public(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "createdAt": self.created_at.isoformat() + "Z",
            "updatedAt": self.updated_at.isoformat() + "Z",
        }


class Provider(TimestampMixin, db.Model):
    __tablename__ = "providers"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("prv"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False, index=True)
    adapter = db.Column(db.String(60), nullable=False)
    base_url = db.Column(db.String(500), nullable=True)
    model = db.Column(db.String(160), nullable=True)
    temperature = db.Column(db.Float, nullable=True)
    max_tokens = db.Column(db.Integer, nullable=True)
    streaming = db.Column(db.Boolean, default=True, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False, index=True)
    config = db.Column(db.JSON, default=dict, nullable=False)
    credential = relationship("ProviderCredential", back_populates="provider", uselist=False, cascade="all, delete-orphan")

    def to_public(self):
        credential = self.credential
        masked = credential.masked_hint if credential else None
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "adapter": self.adapter,
            "baseUrl": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "streaming": self.streaming,
            "enabled": self.enabled,
            "isDefault": self.is_default,
            "config": self.config or {},
            "credential": {
                "configured": bool(credential and (credential.encrypted_api_key or credential.encrypted_access_token)),
                "masked": masked,
                "authMethod": "codex_oauth" if credential and credential.encrypted_access_token else "api_key" if credential and credential.encrypted_api_key else None,
                "accountId": credential.oauth_account_id if credential and credential.encrypted_access_token else None,
                "expiresAt": credential.oauth_expires_at if credential and credential.encrypted_access_token else None,
            },
            "createdAt": self.created_at.isoformat() + "Z",
            "updatedAt": self.updated_at.isoformat() + "Z",
        }


class ProviderCredential(TimestampMixin, db.Model):
    __tablename__ = "provider_credentials"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("cred"))
    provider_id = db.Column(db.String(40), db.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, unique=True)
    encrypted_api_key = db.Column(db.LargeBinary, nullable=True)
    encrypted_access_token = db.Column(db.LargeBinary, nullable=True)
    encrypted_refresh_token = db.Column(db.LargeBinary, nullable=True)
    encrypted_id_token = db.Column(db.LargeBinary, nullable=True)
    oauth_account_id = db.Column(db.String(160), nullable=True)
    oauth_expires_at = db.Column(db.BigInteger, nullable=True)
    oauth_scopes = db.Column(db.JSON, default=list, nullable=False)
    masked_hint = db.Column(db.String(80), nullable=True)
    provider = relationship("Provider", back_populates="credential")


DEFAULT_SETTINGS = {
    "personaName": "Xultron",
    "customInstructions": "",
    "locale": "en",
    "lowDataMode": False,
    "memoryEnabled": True,
    "conversationHistory": True,
    "voiceHistory": False,
    "saveAudio": False,
    "analytics": False,
    "reducedMotion": False,
    "preferredVoice": "",
    "sttLanguage": "auto",
    "timeZone": "UTC",
    "theme": "dark",
    "accent": "cyan",
    "textScale": "standard",
}


class UserSettings(TimestampMixin, db.Model):
    __tablename__ = "user_settings"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("set"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    values = db.Column(db.JSON, default=lambda: dict(DEFAULT_SETTINGS), nullable=False)
    user = relationship("User", back_populates="settings")

    def to_public(self):
        merged = dict(DEFAULT_SETTINGS)
        merged.update(self.values or {})
        return merged


class Device(TimestampMixin, db.Model):
    __tablename__ = "devices"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("dev"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    device_type = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(60), nullable=False, default="offline")
    device_metadata = db.Column("metadata", db.JSON, default=dict, nullable=False)

    def to_public(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.device_type,
            "deviceType": self.device_type,
            "status": self.status,
            "metadata": self.device_metadata or {},
            "createdAt": self.created_at.isoformat() + "Z",
            "updatedAt": self.updated_at.isoformat() + "Z",
        }


class DeviceCommand(TimestampMixin, db.Model):
    __tablename__ = "device_commands"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("cmd"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = db.Column(db.String(40), db.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    command = db.Column(db.String(120), nullable=False)
    payload = db.Column(db.JSON, default=dict, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="queued")
    executed_at = db.Column(db.DateTime, nullable=True)

    def to_public(self):
        return {
            "id": self.id,
            "deviceId": self.device_id,
            "command": self.command,
            "payload": self.payload or {},
            "status": self.status,
            "createdAt": self.created_at.isoformat() + "Z",
            "executedAt": self.executed_at.isoformat() + "Z" if self.executed_at else None,
        }


class DeviceEvent(TimestampMixin, db.Model):
    __tablename__ = "device_events"
    id = db.Column(db.String(40), primary_key=True, default=lambda: new_id("evt"))
    user_id = db.Column(db.String(40), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = db.Column(db.String(40), db.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = db.Column(db.String(120), nullable=False)
    payload = db.Column(db.JSON, default=dict, nullable=False)

    def to_public(self):
        return {
            "id": self.id,
            "deviceId": self.device_id,
            "eventType": self.event_type,
            "payload": self.payload or {},
            "createdAt": self.created_at.isoformat() + "Z",
        }

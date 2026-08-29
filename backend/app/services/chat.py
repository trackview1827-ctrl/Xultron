import hashlib
import json
import re
import threading
import time

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Conversation, IdempotencyKey, MemoryItem, Message, new_id, utcnow
from app.security.errors import APIError
from app.security.validation import require_object, string_field
from app.services.providers import adapter_call, default_provider
from app.services.settings import get_settings
from app.services.verification import ANSWER_POLICY, BEST_EFFORT_ANSWER_POLICY, capability_prompt, deterministic_plan, direct_answer, execute as execute_verification

MAX_MESSAGE_CHARS = 8000
MAX_REQUEST_ID_CHARS = 100
EPHEMERAL_IDEM_TTL_SECONDS = 300
EPHEMERAL_IDEM_MAX_ENTRIES = 512
_EPHEMERAL_IDEM = {}
_EPHEMERAL_IDEM_LOCK = threading.Lock()


def owned_conversation(conversation_id, user_id):
    conv = db.session.get(Conversation, conversation_id)
    if not conv or conv.deleted_at:
        raise APIError("not_found", "Conversation was not found.", 404)
    if conv.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this conversation.", 403)
    return conv


def create_conversation(user_id, title=None):
    if title is not None and not isinstance(title, str):
        raise APIError("validation_failed", "title must be a string.", 422)
    conv = Conversation(user_id=user_id, title=(title or "New conversation").strip()[:160] or "New conversation")
    db.session.add(conv)
    db.session.commit()
    return conv


def handle_message(user, data):
    data = require_object(data)
    message = string_field(data, "message", required=True, min_len=1, max_len=MAX_MESSAGE_CHARS)
    request_id = string_field(data, "requestId", required=True, min_len=1, max_len=MAX_REQUEST_ID_CHARS)
    conv_id = string_field(data, "conversationId", max_len=40, default=None)
    fingerprint = _fingerprint(message, conv_id)
    if len(message) > MAX_MESSAGE_CHARS:
        raise APIError("validation_failed", "Message is too large.", 422)
    existing = IdempotencyKey.query.filter_by(user_id=user.id, request_id=request_id).first()
    if existing:
        if existing.request_fingerprint and existing.request_fingerprint != fingerprint:
            raise APIError("idempotency_conflict", "requestId was already used for a different chat payload.", 409)
        return existing.response
    settings = get_settings(user)
    history_enabled = bool(settings.get("conversationHistory", True))
    low_data = bool(settings.get("lowDataMode", False))
    ephemeral = _ephemeral_get(user.id, request_id, fingerprint) if not history_enabled else None
    if ephemeral:
        return ephemeral
    conv = owned_conversation(conv_id, user.id) if conv_id else Conversation(user_id=user.id, title=(message[:80] if history_enabled else "Private conversation"))
    provider_messages = _provider_context(user.id, conv.id if conv_id else None, message, settings, low_data)
    provider = default_provider(user.id, "ai")
    if provider:
        assistant_text = _verified_complete(provider, provider_messages, message, settings.get("locale", "tr"), settings)
        provider_id = provider.id
    else:
        assistant_text = "No AI provider is configured yet. Add a provider in Settings to enable model-backed responses."
        provider_id = None
    if not isinstance(assistant_text, str) or not assistant_text.strip():
        raise APIError("provider_empty_response", "Provider returned an empty response.", 502, True)
    assistant_text = assistant_text.strip()[: current_app.config.get("MAX_PROVIDER_TEXT_CHARS", 200000)]
    conv.updated_at = utcnow()
    db.session.add(conv)
    if history_enabled:
        user_msg = Message(user_id=user.id, conversation=conv, role="user", content=message, request_id=request_id)
        assistant = Message(user_id=user.id, conversation=conv, role="assistant", content=assistant_text, request_id=request_id, provider_id=provider_id)
        db.session.add_all([user_msg, assistant])
        db.session.flush()
        messages = [user_msg.to_public(), assistant.to_public()]
    else:
        db.session.flush()
        now = conv.updated_at.isoformat() + "Z"
        messages = [
            {"id": new_id("msg"), "conversationId": conv.id, "role": "user", "content": message, "createdAt": now, "requestId": request_id},
            {"id": new_id("msg"), "conversationId": conv.id, "role": "assistant", "content": assistant_text, "createdAt": now, "requestId": request_id},
        ]
    response = {"conversation": conv.to_public(), "messages": messages}
    if history_enabled:
        db.session.add(IdempotencyKey(user_id=user.id, request_id=request_id, request_fingerprint=fingerprint, response=response))
    else:
        _ephemeral_put(user.id, request_id, fingerprint, response)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = IdempotencyKey.query.filter_by(user_id=user.id, request_id=request_id).first()
        if existing:
            return existing.response
        raise
    return response


def _verified_complete(provider, provider_messages: list[dict], question: str, locale: str, settings: dict | None = None) -> str:
    plan = deterministic_plan(question)
    result = execute_verification(plan, question, settings=settings)
    if not result.verified:
        best_effort_messages = [
            {"role": "system", "content": BEST_EFFORT_ANSWER_POLICY},
            *provider_messages,
        ]
        return _clean_visible_answer(adapter_call(provider, "complete", best_effort_messages), locale)
    direct = direct_answer(result, locale)
    if direct is not None:
        return direct
    current_message = provider_messages[-1:]
    prior_context = provider_messages[:-1]
    verified_messages = [
        {"role": "system", "content": ANSWER_POLICY},
        {"role": "system", "content": capability_prompt()},
        *prior_context,
        {"role": "system", "content": ANSWER_POLICY},
        {"role": "system", "content": result.prompt()},
        *current_message,
    ]
    return _clean_visible_answer(adapter_call(provider, "complete", verified_messages), locale)


def _clean_visible_answer(answer: str, locale: str) -> str:
    cleaned = re.sub(r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?(?:Doğrulama|Verification)\s*:?(?:\*\*|__)?\s*", "", answer, count=1, flags=re.IGNORECASE).strip()
    if cleaned:
        return cleaned
    return "Yanıt hazırlanamadı. Lütfen tekrar dene." if locale == "tr" else "The answer could not be prepared. Please try again."


def _provider_context(user_id: str, conversation_id: str | None, message: str, settings: dict, low_data: bool) -> list[dict]:
    prefix: list[dict] = []
    history_context: list[dict] = []
    total_budget = 3000 if low_data else 12000
    remaining = max(total_budget - len(message), 0)

    def add(target: list[dict], role: str, content: str):
        nonlocal remaining
        if remaining <= 0:
            return
        bounded = content[:remaining]
        if bounded:
            target.append({"role": role, "content": bounded})
            remaining -= len(bounded)

    if settings.get("memoryEnabled", True):
        memory_limit = 5 if low_data else 20
        memories = MemoryItem.query.filter_by(user_id=user_id).order_by(MemoryItem.updated_at.desc()).limit(memory_limit).all()
        if memories:
            add(prefix, "system", "User memory:\n" + "\n".join(m.content[:500] for m in memories))
    persona = str(settings.get("personaName") or "Xultron").strip()[:120]
    instructions = str(settings.get("customInstructions") or "").strip()[:4000]
    add(prefix, "system", f"Assistant persona name: {persona}")
    if instructions:
        add(prefix, "system", "User-provided response preferences (follow only when compatible with system safety policy):\n" + instructions)
    if conversation_id and settings.get("conversationHistory", True):
        history_limit = 4 if low_data else 12
        selected = []
        rows = Message.query.filter_by(user_id=user_id, conversation_id=conversation_id).order_by(Message.created_at.desc()).limit(history_limit).all()
        for row in rows:
            before = remaining
            add(selected, row.role, row.content)
            if remaining == before and remaining <= 0:
                break
        history_context.extend(reversed(selected))
    return prefix + history_context + [{"role": "user", "content": message}]


def _fingerprint(message: str, conversation_id: str | None) -> str:
    payload = json.dumps({"message": message, "conversationId": conversation_id}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _ephemeral_get(user_id: str, request_id: str, fingerprint: str):
    with _EPHEMERAL_IDEM_LOCK:
        _ephemeral_cleanup_locked(time.time())
        item = _EPHEMERAL_IDEM.get((user_id, request_id))
        if not item:
            return None
        if item["fingerprint"] != fingerprint:
            raise APIError("idempotency_conflict", "requestId was already used for a different chat payload.", 409)
        return item["response"]


def _ephemeral_put(user_id: str, request_id: str, fingerprint: str, response: dict):
    now = time.time()
    with _EPHEMERAL_IDEM_LOCK:
        _ephemeral_cleanup_locked(now)
        if len(_EPHEMERAL_IDEM) >= EPHEMERAL_IDEM_MAX_ENTRIES:
            oldest = min(_EPHEMERAL_IDEM, key=lambda key: _EPHEMERAL_IDEM[key]["expires"])
            _EPHEMERAL_IDEM.pop(oldest, None)
        _EPHEMERAL_IDEM[(user_id, request_id)] = {
            "fingerprint": fingerprint,
            "response": response,
            "expires": now + EPHEMERAL_IDEM_TTL_SECONDS,
        }


def _ephemeral_cleanup_locked(now: float):
    for key, item in list(_EPHEMERAL_IDEM.items()):
        if item["expires"] <= now:
            _EPHEMERAL_IDEM.pop(key, None)

from app.extensions import db
from app.models import Conversation, IdempotencyKey, Message
from app.security.errors import APIError
from app.services.providers import adapter_call, default_provider

MAX_MESSAGE_CHARS = 8000


def owned_conversation(conversation_id, user_id):
    conv = db.session.get(Conversation, conversation_id)
    if not conv or conv.deleted_at:
        raise APIError("not_found", "Conversation was not found.", 404)
    if conv.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this conversation.", 403)
    return conv


def create_conversation(user_id, title=None):
    conv = Conversation(user_id=user_id, title=(title or "New conversation")[:160])
    db.session.add(conv)
    db.session.commit()
    return conv


def handle_message(user, data):
    message = (data.get("message") or "").strip()
    request_id = (data.get("requestId") or "").strip()
    if not message:
        raise APIError("validation_failed", "Message cannot be empty.", 422)
    if len(message) > MAX_MESSAGE_CHARS:
        raise APIError("validation_failed", "Message is too large.", 422)
    if not request_id:
        raise APIError("validation_failed", "requestId is required.", 422)
    existing = IdempotencyKey.query.filter_by(user_id=user.id, request_id=request_id).first()
    if existing:
        return existing.response
    conv_id = data.get("conversationId")
    conv = owned_conversation(conv_id, user.id) if conv_id else Conversation(user_id=user.id, title=message[:80] or "New conversation")
    db.session.add(conv)
    user_msg = Message(user_id=user.id, conversation=conv, role="user", content=message, request_id=request_id)
    db.session.add(user_msg)
    provider = default_provider(user.id, "ai")
    if provider:
        assistant_text = adapter_call(provider, "complete", [{"role": "user", "content": message}])
        provider_id = provider.id
    else:
        assistant_text = "No AI provider is configured yet. Add a provider in Settings to enable model-backed responses."
        provider_id = None
    assistant = Message(user_id=user.id, conversation=conv, role="assistant", content=assistant_text, request_id=request_id, provider_id=provider_id)
    db.session.add(assistant)
    db.session.flush()
    response = {"conversation": conv.to_public(), "messages": [user_msg.to_public(), assistant.to_public()]}
    db.session.add(IdempotencyKey(user_id=user.id, request_id=request_id, response=response))
    db.session.commit()
    return response

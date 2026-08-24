import json
from datetime import UTC, datetime

from flask import Blueprint, Response, current_app, g, jsonify, request, session

from app.extensions import db
from app.models import Conversation, Device, MemoryItem, Message, Provider, Session, utcnow
from app.security.errors import APIError
from app.security.guards import require_json, require_user
from app.services.auth import cleanup_expired, create_guest, ensure_csrf, login, logout, register
from app.services.chat import create_conversation, handle_message, owned_conversation
from app.services.providers import adapter_call, create_provider, default_provider, update_provider, _owned as owned_provider
from app.services.settings import get_settings, patch_settings

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
MEMORY_CATEGORIES = {"personal", "preferences", "important", "temporary"}


def ok(payload=None, status=200):
    return jsonify(payload or {}), status


@api_bp.get("/system/health")
def health():
    return ok({"status": "online", "version": current_app.config.get("VERSION", "0.1.0"), "time": datetime.now(UTC).isoformat().replace("+00:00", "Z")})


@api_bp.get("/auth/session")
def auth_session():
    token = ensure_csrf()
    user = g.current_user.to_public() if g.get("current_user") else None
    expires = g.current_session.expires_at.isoformat() + "Z" if g.get("current_session") else None
    return ok({"user": user, "csrfToken": token, "expiresAt": expires})


@api_bp.post("/auth/guest")
def auth_guest():
    user, rec = create_guest()
    return ok({"user": user.to_public(), "expiresAt": rec.expires_at.isoformat() + "Z"}, 201)


@api_bp.post("/auth/register")
def auth_register():
    user = register(require_json())
    return ok({"user": user.to_public(), "csrfToken": session.get("csrf_token")}, 201)


@api_bp.post("/auth/login")
def auth_login():
    user = login(require_json())
    return ok({"user": user.to_public(), "csrfToken": session.get("csrf_token")})


@api_bp.post("/auth/logout")
def auth_logout():
    logout()
    return ok({"ok": True})


@api_bp.get("/auth/sessions")
def auth_sessions():
    user = require_user()
    sessions = Session.query.filter_by(user_id=user.id).filter(Session.revoked_at.is_(None), Session.expires_at > utcnow()).order_by(Session.created_at.desc()).all()
    return ok({"sessions": [s.to_public(session.get("sid")) for s in sessions]})


@api_bp.delete("/auth/sessions/<session_id>")
def auth_revoke_session(session_id):
    user = require_user()
    rec = db.session.get(Session, session_id)
    if not rec:
        raise APIError("not_found", "Session was not found.", 404)
    if rec.user_id != user.id:
        raise APIError("forbidden", "You do not have access to this session.", 403)
    rec.revoked_at = utcnow()
    db.session.commit()
    if session.get("sid") == rec.id:
        session.pop("sid", None)
    return ok({"ok": True})


@api_bp.get("/chat/conversations")
def list_conversations():
    user = require_user()
    limit = min(int(request.args.get("limit", 20)), 100)
    rows = Conversation.query.filter_by(user_id=user.id, deleted_at=None).order_by(Conversation.updated_at.desc()).limit(limit).all()
    return ok({"conversations": [c.to_public() for c in rows]})


@api_bp.post("/chat/conversations")
def post_conversation():
    user = require_user()
    data = require_json()
    conv = create_conversation(user.id, data.get("title"))
    return ok({"conversation": conv.to_public()}, 201)


@api_bp.get("/chat/conversations/<conversation_id>")
def get_conversation(conversation_id):
    user = require_user()
    conv = owned_conversation(conversation_id, user.id)
    return ok({"conversation": conv.to_public()})


@api_bp.delete("/chat/conversations/<conversation_id>")
def delete_conversation(conversation_id):
    user = require_user()
    conv = owned_conversation(conversation_id, user.id)
    conv.deleted_at = utcnow()
    db.session.commit()
    return ok({"ok": True})


@api_bp.get("/chat/conversations/<conversation_id>/messages")
def get_messages(conversation_id):
    user = require_user()
    owned_conversation(conversation_id, user.id)
    limit = min(int(request.args.get("limit", 50)), 200)
    rows = Message.query.filter_by(user_id=user.id, conversation_id=conversation_id).order_by(Message.created_at.asc()).limit(limit).all()
    return ok({"messages": [m.to_public() for m in rows]})


@api_bp.post("/chat/messages")
def post_message():
    user = require_user()
    return ok(handle_message(user, require_json()), 201)


@api_bp.post("/chat/stream")
def stream_message():
    user = require_user()
    data = require_json()

    def events():
        started = False
        try:
            yield _sse("state", {"state": "THINKING"}); started = True
            response = handle_message(user, data)
            yield _sse("conversation", response["conversation"])
            text = response["messages"][-1]["content"]
            for token in text.split(" "):
                yield _sse("delta", {"text": token + " "})
            yield _sse("done", response)
        except APIError as exc:
            yield _sse("error", {"code": exc.code, "message": exc.message, "retryable": exc.retryable})
            if started:
                yield _sse("done", {"ok": False})

    return Response(events(), mimetype="text/event-stream")


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@api_bp.get("/providers")
def list_providers():
    user = require_user()
    q = Provider.query.filter_by(user_id=user.id)
    if request.args.get("kind"):
        q = q.filter_by(kind=request.args["kind"])
    return ok({"providers": [p.to_public() for p in q.order_by(Provider.created_at.desc()).all()]})


@api_bp.post("/providers")
def providers_create():
    user = require_user()
    provider = create_provider(user.id, require_json())
    return ok({"provider": provider.to_public()}, 201)


@api_bp.get("/providers/<provider_id>")
def providers_get(provider_id):
    user = require_user()
    return ok({"provider": owned_provider(provider_id, user.id).to_public()})


@api_bp.patch("/providers/<provider_id>")
def providers_patch(provider_id):
    user = require_user()
    return ok({"provider": update_provider(provider_id, user.id, require_json()).to_public()})


@api_bp.delete("/providers/<provider_id>")
def providers_delete(provider_id):
    user = require_user()
    provider = owned_provider(provider_id, user.id)
    db.session.delete(provider)
    db.session.commit()
    return ok({"ok": True})


@api_bp.post("/providers/<provider_id>/test")
def providers_test(provider_id):
    user = require_user()
    provider = owned_provider(provider_id, user.id)
    return ok(adapter_call(provider, "test"))


@api_bp.post("/providers/<provider_id>/models")
def providers_models(provider_id):
    user = require_user()
    provider = owned_provider(provider_id, user.id)
    return ok({"models": adapter_call(provider, "models")})


@api_bp.post("/voice/transcribe")
def transcribe():
    user = require_user()
    f = request.files.get("audio")
    if not f:
        raise APIError("validation_failed", "audio file is required.", 422)
    audio = f.read(current_app.config["MAX_AUDIO_BYTES"] + 1)
    if len(audio) > current_app.config["MAX_AUDIO_BYTES"]:
        raise APIError("request_entity_too_large", "Audio is too large.", 413)
    provider = owned_provider(request.form["providerId"], user.id) if request.form.get("providerId") else default_provider(user.id, "stt")
    if not provider:
        raise APIError("provider_not_configured", "No STT provider is configured.", 503)
    return ok(adapter_call(provider, "transcribe", audio, f.filename, request.form.get("language")))


@api_bp.post("/voice/synthesize")
def synthesize():
    user = require_user()
    data = require_json()
    text = (data.get("text") or "").strip()
    if not text:
        raise APIError("validation_failed", "text is required.", 422)
    if len(text) > 4000:
        raise APIError("validation_failed", "Text is too large.", 422)
    provider = owned_provider(data["providerId"], user.id) if data.get("providerId") else default_provider(user.id, "tts")
    if not provider:
        raise APIError("provider_not_configured", "No TTS provider is configured.", 503)
    audio, media_type = adapter_call(provider, "synthesize", text, data.get("voice"))
    if len(audio) > current_app.config["MAX_AUDIO_BYTES"]:
        raise APIError("request_entity_too_large", "Audio response is too large.", 413)
    return Response(audio, mimetype=media_type)


@api_bp.get("/memory")
def memory_list():
    user = require_user()
    q = MemoryItem.query.filter_by(user_id=user.id)
    if request.args.get("category"):
        q = q.filter_by(category=request.args["category"])
    if request.args.get("query"):
        term = f"%{request.args['query']}%"
        q = q.filter((MemoryItem.title.ilike(term)) | (MemoryItem.content.ilike(term)))
    return ok({"memories": [m.to_public() for m in q.order_by(MemoryItem.updated_at.desc()).all()]})


@api_bp.post("/memory")
def memory_create():
    user = require_user()
    data = require_json()
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    category = data.get("category") or "personal"
    if not title or not content or category not in MEMORY_CATEGORIES:
        raise APIError("validation_failed", "Valid title, content and category are required.", 422)
    item = MemoryItem(user_id=user.id, title=title[:160], content=content, category=category)
    db.session.add(item)
    db.session.commit()
    return ok({"memory": item.to_public()}, 201)


def owned_memory(memory_id, user_id):
    item = db.session.get(MemoryItem, memory_id)
    if not item:
        raise APIError("not_found", "Memory item was not found.", 404)
    if item.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this memory item.", 403)
    return item


@api_bp.get("/memory/<memory_id>")
def memory_get(memory_id):
    user = require_user()
    return ok({"memory": owned_memory(memory_id, user.id).to_public()})


@api_bp.patch("/memory/<memory_id>")
def memory_patch(memory_id):
    user = require_user()
    item = owned_memory(memory_id, user.id)
    data = require_json()
    if "title" in data:
        item.title = (data["title"] or "").strip()[:160]
    if "content" in data:
        item.content = (data["content"] or "").strip()
    if "category" in data:
        if data["category"] not in MEMORY_CATEGORIES:
            raise APIError("validation_failed", "Invalid memory category.", 422)
        item.category = data["category"]
    db.session.commit()
    return ok({"memory": item.to_public()})


@api_bp.delete("/memory/<memory_id>")
def memory_delete(memory_id):
    user = require_user()
    item = owned_memory(memory_id, user.id)
    db.session.delete(item)
    db.session.commit()
    return ok({"ok": True})


@api_bp.delete("/memory")
def memory_clear():
    user = require_user()
    if require_json().get("confirm") != "CLEAR":
        raise APIError("confirmation_required", "Confirmation is required to clear memory.", 422)
    MemoryItem.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    return ok({"ok": True})


@api_bp.get("/settings")
def settings_get():
    return ok({"settings": get_settings(require_user())})


@api_bp.patch("/settings")
def settings_patch():
    return ok({"settings": patch_settings(require_user(), require_json())})


@api_bp.get("/devices")
def devices_get():
    user = require_user()
    devices = Device.query.filter_by(user_id=user.id).order_by(Device.created_at.desc()).all()
    return ok({"devices": [d.to_public() for d in devices]})


@api_bp.cli.command("cleanup-expired")
def cleanup_expired_cmd():
    print(cleanup_expired())

import json
from datetime import UTC, datetime

from flask import Blueprint, Response, current_app, g, jsonify, request, session, stream_with_context
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Conversation, Device, DeviceCommand, DeviceEvent, MemoryItem, Message, Provider, Session, Task, User, utcnow
from app.security.errors import APIError
from app.security.guards import require_json, require_user
from app.security.validation import enum_field, string_field
from app.services.auth import cleanup_expired, create_guest, ensure_csrf, login, logout, register
from app.services.chat import create_conversation, handle_message, owned_conversation
from app.services.providers import adapter_call, create_provider, default_provider, update_provider, _owned as owned_provider
from app.services.openai_oauth import callback as openai_oauth_callback, start as start_openai_oauth
from app.services.settings import get_settings, patch_settings
from app.services.verification import tool_descriptions
from app.services.tasks import claim_task, create_task, execute_task, owned_task, update_task
from app.services.planner import approve_plan, generate_plan

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
MEMORY_CATEGORIES = {"personal", "preferences", "important", "temporary"}
PROVIDER_KINDS = {"ai", "stt", "tts"}
DEVICE_STATUSES = {"offline", "online", "paired", "error"}


def ok(payload=None, status=200):
    return jsonify(payload or {}), status


def query_limit(default: int, max_value: int) -> int:
    raw = request.args.get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise APIError("validation_failed", "limit must be an integer.", 422)
    if value < 1 or value > max_value:
        raise APIError("validation_failed", "limit is out of range.", 422)
    return value


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
    return ok({"user": user.to_public(), "csrfToken": session.get("csrf_token"), "expiresAt": rec.expires_at.isoformat() + "Z"}, 201)


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
    token = ensure_csrf()
    return ok({"ok": True, "csrfToken": token})


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
    limit = query_limit(20, 100)
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
    limit = query_limit(50, 200)
    rows = Message.query.filter_by(user_id=user.id, conversation_id=conversation_id).order_by(Message.created_at.desc()).limit(limit).all()
    return ok({"messages": [m.to_public() for m in reversed(rows)]})


@api_bp.post("/chat/messages")
def post_message():
    user = require_user()
    return ok(handle_message(user, require_json()), 201)


@api_bp.post("/chat/stream")
def stream_message():
    user = require_user()
    data = require_json()
    user_id = user.id
    request_id = request.request_id

    def events():
        try:
            # The original request teardown can detach ORM objects before a streamed
            # generator runs. Reload the identity inside the active stream context.
            stream_user = db.session.get(User, user_id)
            if not stream_user:
                raise APIError("authentication_required", "Authentication is required.", 401)
            yield _sse("state", {"state": "THINKING"})
            response = handle_message(stream_user, data)
            yield _sse("conversation", response["conversation"])
            text = response["messages"][-1]["content"]
            for token in text.split(" "):
                yield _sse("delta", {"text": token + " "})
            yield _sse("done", response)
        except APIError as exc:
            yield _sse("error", {"code": exc.code, "message": exc.message, "retryable": exc.retryable})
            yield _sse("done", {"ok": False})
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error("Unhandled SSE error type=%s request_id=%s", type(exc).__name__, request_id)
            yield _sse("error", {"code": "internal_error", "message": "An internal error occurred.", "retryable": False})
            yield _sse("done", {"ok": False})

    response = Response(stream_with_context(events()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    return response


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@api_bp.get("/providers")
def list_providers():
    user = require_user()
    q = Provider.query.filter_by(user_id=user.id)
    if request.args.get("kind"):
        if request.args["kind"] not in PROVIDER_KINDS:
            raise APIError("validation_failed", "kind is invalid.", 422)
        q = q.filter_by(kind=request.args["kind"])
    return ok({"providers": [p.to_public() for p in q.order_by(Provider.created_at.desc()).all()]})


@api_bp.get("/tools")
def list_tools():
    """Expose capability metadata without exposing credentials or handlers."""
    require_user()
    return ok({"tools": tool_descriptions()})


@api_bp.get("/tasks")
def list_tasks():
    user = require_user()
    limit = query_limit(20, 100)
    rows = Task.query.filter_by(user_id=user.id).order_by(Task.updated_at.desc()).limit(limit).all()
    return ok({"tasks": [task.to_public() for task in rows]})


@api_bp.post("/tasks")
def post_task():
    return ok({"task": create_task(require_user().id, require_json()).to_public()}, 201)


@api_bp.get("/tasks/<task_id>")
def get_task(task_id):
    return ok({"task": owned_task(task_id, require_user().id).to_public()})


@api_bp.patch("/tasks/<task_id>")
def patch_task(task_id):
    task = owned_task(task_id, require_user().id)
    return ok({"task": update_task(task, require_json()).to_public()})


@api_bp.post("/tasks/<task_id>/cancel")
def cancel_task_route(task_id):
    task = owned_task(task_id, require_user().id)
    return ok({"task": update_task(task, {"status": "cancelled"}).to_public()})


@api_bp.post("/tasks/<task_id>/claim")
def claim_task_route(task_id):
    task = owned_task(task_id, require_user().id)
    data = require_json()
    return ok({"task": claim_task(task, data.get("workerId")).to_public()})


@api_bp.post("/tasks/<task_id>/execute")
def execute_task_route(task_id):
    task = owned_task(task_id, require_user().id)
    data = require_json()
    return ok({"task": execute_task(task, data.get("workerId")).to_public()})


@api_bp.post("/tasks/<task_id>/plan")
def plan_task_route(task_id):
    user = require_user()
    task = owned_task(task_id, user.id)
    return ok({"task": generate_plan(task, user.id).to_public()})


@api_bp.post("/tasks/<task_id>/plan/approve")
def approve_task_plan_route(task_id):
    user = require_user()
    return ok({"task": approve_plan(owned_task(task_id, user.id), user.id).to_public()})


@api_bp.get("/tasks/<task_id>/plan")
def get_task_plan_route(task_id):
    task = owned_task(task_id, require_user().id)
    return ok({"plan": (task.result or {}).get("plan")})


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


@api_bp.post("/providers/<provider_id>/oauth/openai/start")
def providers_openai_oauth_start(provider_id):
    user = require_user()
    provider = owned_provider(provider_id, user.id)
    if provider.kind != "ai" or provider.adapter != "openai_codex_oauth":
        raise APIError("oauth_not_supported", "This provider is not configured for Codex OAuth.", 422)
    return ok(start_openai_oauth(provider))


@api_bp.get("/providers/oauth/openai/callback")
def providers_openai_oauth_callback():
    return openai_oauth_callback()


@api_bp.post("/voice/transcribe")
def transcribe():
    user = require_user()
    f = request.files.get("audio")
    if not f:
        raise APIError("validation_failed", "audio file is required.", 422)
    if f.mimetype and not (f.mimetype.startswith("audio/") or f.mimetype in {"application/octet-stream", "video/webm"}):
        raise APIError("unsupported_audio_type", "Audio type is not supported.", 422)
    audio = f.read(current_app.config["MAX_AUDIO_BYTES"] + 1)
    if not audio:
        raise APIError("invalid_audio", "Audio is empty.", 422)
    if len(audio) > current_app.config["MAX_AUDIO_BYTES"]:
        raise APIError("request_entity_too_large", "Audio is too large.", 413)
    provider_id = request.form.get("providerId")
    language = request.form.get("language")
    if provider_id is not None and (not isinstance(provider_id, str) or len(provider_id.strip()) > 40):
        raise APIError("validation_failed", "providerId is invalid.", 422)
    if language is not None and (not isinstance(language, str) or len(language.strip()) > 40):
        raise APIError("validation_failed", "language is invalid.", 422)
    provider = owned_provider(provider_id.strip(), user.id) if provider_id and provider_id.strip() else default_provider(user.id, "stt")
    if not provider:
        raise APIError("provider_not_configured", "No STT provider is configured.", 503)
    filename = secure_filename(f.filename or "")[:120] or "audio.webm"
    return ok(adapter_call(provider, "transcribe", audio, filename, language.strip() if language else None))


@api_bp.post("/voice/synthesize")
def synthesize():
    user = require_user()
    data = require_json()
    text = string_field(data, "text", required=True, min_len=1, max_len=4000)
    if len(text) > 4000:
        raise APIError("validation_failed", "Text is too large.", 422)
    provider_id = string_field(data, "providerId", max_len=40, default=None)
    voice = string_field(data, "voice", max_len=120, default=None)
    provider = owned_provider(provider_id, user.id) if provider_id else default_provider(user.id, "tts")
    if not provider:
        raise APIError("provider_not_configured", "No TTS provider is configured.", 503)
    audio, media_type = adapter_call(provider, "synthesize", text, voice)
    if len(audio) > current_app.config["MAX_AUDIO_BYTES"]:
        raise APIError("request_entity_too_large", "Audio response is too large.", 413)
    return Response(audio, mimetype=media_type)


@api_bp.get("/memory")
def memory_list():
    user = require_user()
    q = MemoryItem.query.filter_by(user_id=user.id)
    if request.args.get("category"):
        if request.args["category"] not in MEMORY_CATEGORIES:
            raise APIError("validation_failed", "category is invalid.", 422)
        q = q.filter_by(category=request.args["category"])
    if request.args.get("query"):
        if len(request.args["query"]) > 120:
            raise APIError("validation_failed", "query is too long.", 422)
        term = f"%{request.args['query'].strip()}%"
        q = q.filter((MemoryItem.title.ilike(term)) | (MemoryItem.content.ilike(term)))
    return ok({"memories": [m.to_public() for m in q.order_by(MemoryItem.updated_at.desc()).all()]})


@api_bp.post("/memory")
def memory_create():
    user = require_user()
    data = require_json()
    title = string_field(data, "title", required=True, min_len=1, max_len=160)
    content = string_field(data, "content", required=True, min_len=1, max_len=8000)
    category = enum_field(data, "category", MEMORY_CATEGORIES, default="personal") or "personal"
    item = MemoryItem(user_id=user.id, title=title, content=content, category=category)
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
        item.title = string_field(data, "title", required=True, min_len=1, max_len=160)
    if "content" in data:
        item.content = string_field(data, "content", required=True, min_len=1, max_len=8000)
    if "category" in data:
        item.category = enum_field(data, "category", MEMORY_CATEGORIES, required=True)
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


def owned_device(device_id, user_id):
    device = db.session.get(Device, device_id)
    if not device:
        raise APIError("not_found", "Device was not found.", 404)
    if device.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this device.", 403)
    return device


@api_bp.post("/devices")
def devices_create():
    user = require_user()
    data = require_json()
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise APIError("validation_failed", "metadata must be an object.", 422)
    device = Device(
        user_id=user.id,
        name=string_field(data, "name", required=True, min_len=1, max_len=120),
        device_type=string_field(data, "type", required=True, min_len=1, max_len=60),
        status=enum_field(data, "status", DEVICE_STATUSES, default="offline") or "offline",
        device_metadata=metadata,
    )
    db.session.add(device)
    db.session.commit()
    return ok({"device": device.to_public()}, 201)


@api_bp.post("/devices/<device_id>/commands")
def device_command_create(device_id):
    user = require_user()
    device = owned_device(device_id, user.id)
    data = require_json()
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise APIError("validation_failed", "payload must be an object.", 422)
    cmd = DeviceCommand(user_id=user.id, device_id=device.id, command=string_field(data, "command", required=True, min_len=1, max_len=120), payload=payload)
    db.session.add(cmd)
    db.session.commit()
    return ok({"command": cmd.to_public()}, 201)


@api_bp.get("/devices/<device_id>/events")
def device_events(device_id):
    user = require_user()
    device = owned_device(device_id, user.id)
    limit = query_limit(50, 200)
    events = DeviceEvent.query.filter_by(user_id=user.id, device_id=device.id).order_by(DeviceEvent.created_at.desc()).limit(limit).all()
    return ok({"events": [event.to_public() for event in events]})


@api_bp.cli.command("cleanup-expired")
def cleanup_expired_cmd():
    print(cleanup_expired())

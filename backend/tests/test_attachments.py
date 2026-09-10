import base64
from types import SimpleNamespace
from io import BytesIO

from app.extensions import db
from app.models import Attachment
from tests.conftest import post_json, register


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL7WAAAAABJRU5ErkJggg=="
)


def upload_attachment(client, data, filename, content_type):
    token = client.get("/api/v1/auth/session").get_json()["csrfToken"]
    return client.post(
        "/api/v1/attachments",
        data={"file": (BytesIO(data), filename, content_type)},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )


def test_attachment_upload_is_opaque_bounded_and_rejects_uninspectable_binary(user_client):
    uploaded = upload_attachment(user_client, b"hello\nworld", "notes.txt", "text/plain")
    assert uploaded.status_code == 201
    attachment = uploaded.get_json()["attachment"]
    assert attachment["id"].startswith("att_")
    assert attachment["state"] == "ready"
    assert attachment["kind"] == "text"
    assert attachment["size"] == 11
    assert attachment["text"] == "hello\nworld"

    video = upload_attachment(user_client, b"not-a-video", "clip.mp4", "video/mp4")
    assert video.status_code == 422
    assert video.get_json()["error"]["code"] == "unsupported_attachment"

    invalid_image = upload_attachment(user_client, b"not-an-image", "screen.png", "image/png")
    assert invalid_image.status_code == 422
    assert invalid_image.get_json()["error"]["code"] == "unsupported_attachment"


def test_video_attachment_extracts_a_bounded_visual_frame_for_supported_provider(user_client, monkeypatch):
    """The model receives the derived frame, never an unvalidated video blob."""
    captured = {}

    def fake_run(args, **_kwargs):
        # The extraction helper supplies a temp output path as the final argument.
        from pathlib import Path
        Path(args[-1]).write_bytes(PNG_1X1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.attachments.shutil.which", lambda _name: "/safe/ffmpeg")
    monkeypatch.setattr("app.services.attachments.subprocess.run", fake_run)
    uploaded = upload_attachment(user_client, b"video-source", "clip.mp4", "video/mp4")
    assert uploaded.status_code == 201
    attachment = uploaded.get_json()["attachment"]
    assert attachment["kind"] == "video"

    class Response:
        status_code = 200
        headers = {}
        encoding = "utf-8"
        def iter_content(self, chunk_size):
            yield b'{"choices":[{"message":{"content":"video described"}}]}'
        def close(self):
            pass

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    provider = post_json(user_client, "/api/v1/providers", {
        "name": "Vision", "kind": "ai", "adapter": "openai_compatible",
        "baseUrl": "https://provider.example.test/v1", "model": "vision-model", "isDefault": True,
    })
    assert provider.status_code == 201
    response = post_json(user_client, "/api/v1/chat/messages", {
        "message": "Describe this video", "requestId": "video-1", "attachmentIds": [attachment["id"]],
    })
    assert response.status_code == 201
    content = captured["json"]["messages"][-1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert b"video-source" not in str(captured["json"]).encode()


def test_chat_attachment_metadata_is_safe_and_idempotent(user_client):
    uploaded = upload_attachment(user_client, b"private attachment text", "notes.txt", "text/plain")
    attachment = uploaded.get_json()["attachment"]
    payload = {"message": "Summarize this", "requestId": "attachment-idem", "attachmentIds": [attachment["id"]]}

    first = post_json(user_client, "/api/v1/chat/messages", payload)
    assert first.status_code == 201
    user_message = first.get_json()["messages"][0]
    assert user_message["attachments"] == [{key: attachment[key] for key in ("id", "name", "contentType", "kind", "state", "size", "sha256", "extraction")}]
    assert "private attachment text" not in user_message["attachments"]
    assert user_message["content"] == "Summarize this"

    retry = post_json(user_client, "/api/v1/chat/messages", payload)
    assert retry.status_code == 201
    assert retry.get_json() == first.get_json()

    changed = post_json(
        user_client,
        "/api/v1/chat/messages",
        {"message": "Summarize this", "requestId": "attachment-idem", "attachmentIds": []},
    )
    assert changed.status_code == 409
    assert changed.get_json()["error"]["code"] == "idempotency_conflict"

    conversation_id = first.get_json()["conversation"]["id"]
    history = user_client.get(f"/api/v1/chat/conversations/{conversation_id}/messages").get_json()["messages"]
    assert history[0]["attachments"] == user_message["attachments"]
    assert "private attachment text" not in str(history[0]["attachments"])

    duplicate = post_json(
        user_client,
        "/api/v1/chat/messages",
        {"message": "duplicate", "requestId": "attachment-duplicate", "attachmentIds": [attachment["id"], attachment["id"]]},
    )
    assert duplicate.status_code == 422
    assert duplicate.get_json()["error"]["code"] == "validation_failed"


def test_chat_rejects_other_users_and_non_ready_attachment(user_client, app):
    uploaded = upload_attachment(user_client, b"owned", "notes.txt", "text/plain")
    attachment_id = uploaded.get_json()["attachment"]["id"]
    other = app.test_client()
    register(other, "bob", "bob@example.com", "password123")

    forbidden = post_json(other, "/api/v1/chat/messages", {"message": "use it", "requestId": "other-owner", "attachmentIds": [attachment_id]})
    assert forbidden.status_code == 403
    assert forbidden.get_json()["error"]["code"] == "forbidden"

    with app.app_context():
        attachment = db.session.get(Attachment, attachment_id)
        attachment.state = "rejected"
        db.session.commit()
    not_ready = post_json(user_client, "/api/v1/chat/messages", {"message": "use it", "requestId": "not-ready", "attachmentIds": [attachment_id]})
    assert not_ready.status_code == 409
    assert not_ready.get_json()["error"]["code"] == "attachment_not_ready"


def test_image_attachment_reaches_openai_compatible_payload(user_client, monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        headers = {}
        encoding = "utf-8"

        def iter_content(self, chunk_size):
            yield b'{"choices":[{"message":{"content":"image described"}}]}'

        def close(self):
            pass

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("app.providers.adapters.requests.post", post)
    provider = post_json(
        user_client,
        "/api/v1/providers",
        {
            "name": "Vision",
            "kind": "ai",
            "adapter": "openai_compatible",
            "baseUrl": "https://provider.example.test/v1",
            "model": "vision-model",
            "isDefault": True,
        },
    )
    assert provider.status_code == 201
    uploaded = upload_attachment(user_client, PNG_1X1, "pixel.png", "image/png")
    assert uploaded.status_code == 201
    attachment_id = uploaded.get_json()["attachment"]["id"]
    text_upload = upload_attachment(user_client, b"provider-visible text", "context.txt", "text/plain")
    assert text_upload.status_code == 201
    text_attachment_id = text_upload.get_json()["attachment"]["id"]

    response = post_json(
        user_client,
        "/api/v1/chat/messages",
        {"message": "Describe this image", "requestId": "vision-1", "attachmentIds": [text_attachment_id, attachment_id]},
    )
    assert response.status_code == 201
    payload = captured["json"]
    assert captured["url"] == "https://provider.example.test/v1/chat/completions"
    content = payload["messages"][-1]["content"]
    assert content[0] == {"type": "text", "text": "Describe this image\n\nAttached text file (context.txt):\nprovider-visible text"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert base64.b64encode(PNG_1X1).decode() not in str(response.get_json()["messages"][0])


def test_image_attachment_requires_openai_compatible_provider(user_client):
    uploaded = upload_attachment(user_client, PNG_1X1, "pixel.png", "image/png")
    attachment_id = uploaded.get_json()["attachment"]["id"]
    response = post_json(
        user_client,
        "/api/v1/chat/messages",
        {"message": "Describe this image", "requestId": "vision-provider-required", "attachmentIds": [attachment_id]},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "unsupported_attachment"

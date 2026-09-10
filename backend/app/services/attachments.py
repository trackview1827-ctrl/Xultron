"""Bounded, user-owned chat attachments and provider-safe content construction."""

from __future__ import annotations

import base64
import hashlib
import shutil
import struct
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Attachment
from app.security.errors import APIError
from app.security.validation import string_field

TEXT_TYPES = frozenset({"text/plain", "text/markdown", "application/json", "text/csv"})
IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif"})
VIDEO_TYPES = frozenset({"video/mp4", "video/webm", "video/quicktime"})
OPENAI_COMPATIBLE_ADAPTERS = frozenset({"openai_compatible", "local_http"})
MAX_ATTACHMENT_ID_CHARS = 40


def create_attachment(user_id: str, upload: FileStorage) -> Attachment:
    """Persist one validated attachment and return its user-owned record.

    The API deliberately does not inspect archives, executables, or arbitrary
    binary content. Text has a bounded UTF-8 extraction path. Images and supported
    videos have bounded structural paths before a visual representation can be sent
    through OpenAI-compatible image content parts.
    """
    if not upload or not upload.filename:
        raise APIError("validation_failed", "file is required.", 422)
    max_bytes = current_app.config["MAX_ATTACHMENT_BYTES"]
    data = upload.read(max_bytes + 1)
    if not data:
        raise APIError("validation_failed", "Attachment is empty.", 422)
    if len(data) > max_bytes:
        raise APIError("payload_too_large", "Attachment is too large.", 413)

    content_type = _content_type(upload.mimetype)
    name = secure_filename(upload.filename)[:255] or "attachment"
    extracted_text = None
    if content_type in TEXT_TYPES:
        try:
            extracted_text = data.decode("utf-8")[: current_app.config["MAX_ATTACHMENT_TEXT_CHARS"]]
        except UnicodeDecodeError:
            raise APIError("unsupported_attachment", "Text attachments must be valid UTF-8.", 422)
        kind = "text"
    elif content_type in IMAGE_TYPES:
        _validate_image(data, content_type, current_app.config["MAX_ATTACHMENT_IMAGE_PIXELS"])
        kind = "image"
        analysis_content = data
        analysis_content_type = content_type
    elif content_type in VIDEO_TYPES:
        kind = "video"
        analysis_content, analysis_content_type = _video_preview(
            data,
            current_app.config["MAX_ATTACHMENT_VIDEO_FRAME_BYTES"],
            current_app.config["MAX_ATTACHMENT_IMAGE_PIXELS"],
            current_app.config["ATTACHMENT_MEDIA_TIMEOUT_SECONDS"],
        )
    else:
        raise APIError(
            "unsupported_attachment",
            "Only UTF-8 text, PNG, JPEG, GIF, MP4, WebM, and MOV attachments are supported.",
            422,
        )

    attachment = Attachment(
        user_id=user_id,
        name=name,
        content_type=content_type,
        kind=kind,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        content=data,
        extracted_text=extracted_text,
        analysis_content=analysis_content if kind in {"image", "video"} else None,
        analysis_content_type=analysis_content_type if kind in {"image", "video"} else None,
    )
    db.session.add(attachment)
    db.session.commit()
    return attachment


def attachment_records(user_id: str, raw_ids: object) -> list[Attachment]:
    """Validate a bounded ID list, ownership, ready state, and aggregate bytes."""
    if raw_ids is None:
        return []
    if not isinstance(raw_ids, list):
        raise APIError("validation_failed", "attachments must be a list.", 422)
    maximum = current_app.config["MAX_ATTACHMENTS_PER_MESSAGE"]
    if len(raw_ids) > maximum:
        raise APIError("validation_failed", f"attachments may contain at most {maximum} items.", 422)

    attachment_ids = []
    for value in raw_ids:
        attachment_id = string_field({"attachmentId": value}, "attachmentId", required=True, max_len=MAX_ATTACHMENT_ID_CHARS)
        if not attachment_id.startswith("att_"):
            raise APIError("validation_failed", "attachmentId is invalid.", 422)
        attachment_ids.append(attachment_id)
    if len(set(attachment_ids)) != len(attachment_ids):
        raise APIError("validation_failed", "attachments must not contain duplicate IDs.", 422)
    if not attachment_ids:
        return []

    rows = Attachment.query.filter(Attachment.id.in_(attachment_ids)).all()
    by_id = {row.id: row for row in rows}
    attachments = []
    for attachment_id in attachment_ids:
        row = by_id.get(attachment_id)
        if not row:
            raise APIError("not_found", "Attachment was not found.", 404)
        if row.user_id != user_id:
            raise APIError("forbidden", "You do not have access to this attachment.", 403)
        if row.state != "ready":
            raise APIError("attachment_not_ready", "Attachment is not ready to use.", 409)
        attachments.append(row)

    if sum(row.size for row in attachments) > current_app.config["MAX_ATTACHMENT_TOTAL_BYTES"]:
        raise APIError("payload_too_large", "Combined attachment size is too large.", 413)
    return attachments


def ensure_provider_supports_attachments(provider, attachments: Iterable[Attachment]) -> None:
    """Reject images unless the selected transport can represent them faithfully."""
    if any(attachment.kind in {"image", "video"} for attachment in attachments):
        if not provider or provider.adapter not in OPENAI_COMPATIBLE_ADAPTERS:
            raise APIError(
                "unsupported_attachment",
                "Image attachments require an OpenAI-compatible AI provider.",
                422,
            )


def provider_user_content(message: str, attachments: Iterable[Attachment], low_data: bool) -> str | list[dict]:
    """Build the current user turn using only formats the chosen provider supports."""
    attachments = list(attachments)
    context_budget = 3000 if low_data else 12000
    attachment_text_budget = min(
        current_app.config["MAX_PROVIDER_ATTACHMENT_TEXT_CHARS"],
        max(context_budget - len(message), 0),
    )
    text = message
    remaining = attachment_text_budget
    for attachment in attachments:
        if attachment.kind != "text" or not remaining:
            continue
        heading = f"\n\nAttached text file ({attachment.name}):\n"
        excerpt_budget = max(remaining - len(heading), 0)
        excerpt = (attachment.extracted_text or "")[:excerpt_budget]
        if heading or excerpt:
            text += heading + excerpt
            remaining -= min(remaining, len(heading) + len(excerpt))

    visuals = [attachment for attachment in attachments if attachment.kind in {"image", "video"}]
    if not visuals:
        return text
    return [
        {"type": "text", "text": text},
        *[
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{attachment.analysis_content_type};base64,{base64.b64encode(attachment.analysis_content or b'').decode('ascii')}",
                },
            }
            for attachment in visuals
        ],
    ]


def public_metadata(attachments: Iterable[Attachment]) -> list[dict]:
    return [attachment.to_public() for attachment in attachments]


def _content_type(value: object) -> str:
    if not isinstance(value, str):
        return "application/octet-stream"
    return value.split(";", 1)[0].strip().lower()[:100] or "application/octet-stream"


def _validate_image(data: bytes, content_type: str, max_pixels: int) -> None:
    if content_type == "image/png":
        if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR" or not data.endswith(b"IEND\xaeB`\x82"):
            _invalid_image()
        width, height = struct.unpack(">II", data[16:24])
    elif content_type == "image/gif":
        if len(data) < 14 or data[:6] not in {b"GIF87a", b"GIF89a"} or data[-1:] != b";":
            _invalid_image()
        width, height = struct.unpack("<HH", data[6:10])
    elif content_type == "image/jpeg":
        width, height = _jpeg_dimensions(data)
    else:  # Kept defensive even though callers gate to IMAGE_TYPES.
        _invalid_image()
    if not width or not height or width * height > max_pixels:
        raise APIError("unsupported_attachment", "Image dimensions are invalid or too large.", 422)


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        _invalid_image()
    pos = 2
    while pos + 9 <= len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[pos:pos + 2])[0]
        if segment_length < 2 or pos + segment_length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_length < 8:
                break
            height, width = struct.unpack(">HH", data[pos + 3:pos + 7])
            return width, height
        pos += segment_length
    _invalid_image()
    raise AssertionError("unreachable")


def _invalid_image() -> None:
    raise APIError("unsupported_attachment", "Image data is invalid or unsupported.", 422)


def _video_preview(data: bytes, max_frame_bytes: int, max_pixels: int, timeout_seconds: int) -> tuple[bytes, str]:
    """Extract a small representative PNG frame with a fixed local FFmpeg binary.

    The original input is already bounded. The process has a hard timeout, receives
    no shell, does not inherit stdin, and emits to an app-private temporary path.
    A missing tool or failed decode is an explicit rejection, never a metadata-only
    success that could imply the video was inspected.
    """
    executable = shutil.which("ffmpeg")
    if not executable:
        raise APIError("unsupported_attachment", "Video analysis requires local FFmpeg support.", 422)
    with tempfile.TemporaryDirectory(prefix="xultron-video-") as directory:
        root = Path(directory)
        source = root / "source"
        preview = root / "frame.png"
        source.write_bytes(data)
        try:
            completed = subprocess.run(
                [
                    executable, "-nostdin", "-v", "error", "-i", str(source),
                    "-map", "0:v:0", "-frames:v", "1",
                    "-vf", "scale=1280:720:force_original_aspect_ratio=decrease",
                    "-y", str(preview),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise APIError("unsupported_attachment", "Video could not be decoded safely.", 422)
        if completed.returncode != 0 or not preview.is_file():
            raise APIError("unsupported_attachment", "Video could not be decoded safely.", 422)
        frame = preview.read_bytes()
    if not frame or len(frame) > max_frame_bytes:
        raise APIError("unsupported_attachment", "Video preview is too large.", 422)
    _validate_image(frame, "image/png", max_pixels)
    return frame, "image/png"

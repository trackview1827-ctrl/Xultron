from app.extensions import db
from app.models import Task, utcnow
from app.security.errors import APIError
from app.security.validation import enum_field, string_field

TASK_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}


def create_task(user_id, data):
    title = string_field(data, "title", required=True, min_len=1, max_len=160)
    instruction = string_field(data, "instruction", required=True, min_len=1, max_len=10000)
    task = Task(user_id=user_id, title=title, instruction=instruction)
    db.session.add(task)
    db.session.commit()
    return task


def owned_task(task_id, user_id):
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        raise APIError("not_found", "Task was not found.", 404)
    return task


def update_task(task, data):
    status = enum_field(data, "status", TASK_STATUSES)
    if status is not None:
        task.status = status
    if "result" in data:
        if not isinstance(data["result"], (dict, list, str, int, float, bool, type(None))):
            raise APIError("validation_failed", "result must be JSON-compatible.", 422)
        task.result = data["result"]
    if "error" in data:
        task.error = string_field(data, "error", max_len=1000)
    task.updated_at = utcnow()
    db.session.commit()
    return task

from app.extensions import db
from datetime import timedelta
from app.models import Task, utcnow
from app.security.errors import APIError
from app.security.validation import enum_field, string_field

TASK_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}
LEASE_SECONDS = 60


def record_event(task, event_type, payload=None):
    result = dict(task.result or {}) if isinstance(task.result, dict) else {}
    events = list(result.get("events") or [])
    events.append({"type": event_type, "payload": payload or {}, "at": utcnow().isoformat() + "Z"})
    result["events"] = events[-100:]
    task.result = result


def create_task(user_id, data):
    title = string_field(data, "title", required=True, min_len=1, max_len=160)
    instruction = string_field(data, "instruction", required=True, min_len=1, max_len=10000)
    task = Task(user_id=user_id, title=title, instruction=instruction)
    record_event(task, "created")
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
        record_event(task, "status_changed", {"status": status})
    if "result" in data:
        if not isinstance(data["result"], (dict, list, str, int, float, bool, type(None))):
            raise APIError("validation_failed", "result must be JSON-compatible.", 422)
        task.result = data["result"]
    if "error" in data:
        task.error = string_field(data, "error", max_len=1000)
    task.updated_at = utcnow()
    db.session.commit()
    return task


def claim_task(task, worker_id, lease_seconds=LEASE_SECONDS):
    """Atomically claim available work; repeating the same claim is harmless."""
    worker_id = string_field({"worker": worker_id}, "worker", required=True, min_len=1, max_len=120)
    now = utcnow()
    if task.status in {"completed", "failed", "cancelled"}:
        raise APIError("task_unavailable", "Task is already terminal.", 409)
    if task.status == "running" and task.lease_expires_at and task.lease_expires_at > now and task.worker_id != worker_id:
        raise APIError("task_claimed", "Task is leased to another worker.", 409)
    task.worker_id = worker_id
    task.status = "running"
    task.lease_expires_at = now + timedelta(seconds=lease_seconds)
    task.updated_at = now
    record_event(task, "claimed", {"workerId": worker_id})
    db.session.commit()
    return task


def execute_task(task, worker_id):
    """Run the deliberately deterministic, side-effect-free worker."""
    if task.status != "running" or task.worker_id != worker_id:
        raise APIError("task_not_claimed", "Worker does not hold the task lease.", 409)
    if task.lease_expires_at and task.lease_expires_at <= utcnow():
        raise APIError("lease_expired", "Task lease has expired.", 409)
    task.status = "completed"
    task.result = {"workerId": worker_id, "instruction": task.instruction, "deterministic": True}
    task.lease_expires_at = None
    task.updated_at = utcnow()
    db.session.commit()
    return task


def recover_expired_tasks():
    now = utcnow()
    rows = Task.query.filter(Task.status == "running", Task.lease_expires_at <= now).all()
    for task in rows:
        task.status = "pending"
        task.worker_id = None
        task.lease_expires_at = None
        task.updated_at = now
        record_event(task, "lease_recovered")
    if rows:
        db.session.commit()
    return rows

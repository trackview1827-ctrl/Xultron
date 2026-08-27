from app.extensions import db
from datetime import timedelta
from app.models import Task, utcnow
from app.security.errors import APIError
from app.security.validation import enum_field, string_field

TASK_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}
LEASE_SECONDS = 60
MAX_LEASE_SECONDS = 3600


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
    if not isinstance(lease_seconds, int) or not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
        raise APIError("validation_failed", "lease_seconds must be between 1 and 3600.", 422)
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


def renew_task(task, worker_id, lease_seconds=LEASE_SECONDS):
    """Extend a live lease without changing ownership or task state."""
    worker_id = string_field({"worker": worker_id}, "worker", required=True, min_len=1, max_len=120)
    if not isinstance(lease_seconds, int) or not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
        raise APIError("validation_failed", "lease_seconds must be between 1 and 3600.", 422)
    now = utcnow()
    if task.status != "running" or task.worker_id != worker_id:
        raise APIError("task_not_claimed", "Worker does not hold the task lease.", 409)
    if task.lease_expires_at and task.lease_expires_at <= now:
        raise APIError("lease_expired", "Task lease has expired.", 409)
    task.lease_expires_at = now + timedelta(seconds=lease_seconds)
    task.updated_at = now
    record_event(task, "lease_renewed", {"workerId": worker_id})
    db.session.commit()
    return task


def execute_task(task, worker_id):
    """Execute only a declared read-only plan and persist the observed result."""
    if task.status != "running" or task.worker_id != worker_id:
        raise APIError("task_not_claimed", "Worker does not hold the task lease.", 409)
    if task.lease_expires_at and task.lease_expires_at <= utcnow():
        raise APIError("lease_expired", "Task lease has expired.", 409)
    plan = (task.result or {}).get("plan") if isinstance(task.result, dict) else None
    if plan and plan.get("status") != "approved":
        raise APIError("plan_not_approved", "The task plan must be approved before execution.", 409)
    result = dict(task.result or {}) if isinstance(task.result, dict) else {}
    if plan:
        from app.services.verification import VerificationPlan, VerificationResult, execute as execute_verification
        tool = plan.get("tool")
        if tool not in {"runtime", "terminal", "project", "web", "calculate", "reasoning"}:
            raise APIError("unsupported_tool", "The approved plan contains no executable registered tool.", 409)
        observed = execute_verification(VerificationPlan(
            tool=tool, operation=plan.get("operation"), query=plan.get("query", task.instruction), reason=plan.get("reason", "")
        ), task.instruction)
        result["observation"] = {"verified": observed.verified, "tool": observed.tool, "summary": observed.summary, "evidence": observed.evidence}
        task.result = result
        record_event(task, "observation_recorded", {"tool": observed.tool, "verified": observed.verified})
        result = dict(task.result)
        if not isinstance(observed, VerificationResult) or not observed.verified:
            task.status = "failed"
            task.error = "Registered tool did not produce verified evidence."
            plan["status"] = "failed"
        else:
            task.status = "completed"
            plan["status"] = "completed"
            for step in plan.get("steps", []):
                step["status"] = "completed"
            record_event(task, "execution_completed", {"workerId": worker_id, "planApproved": True})
        result["plan"] = plan
    else:
        # A literal no-op has no capability or side effect to plan. Preserve
        # the deterministic completion path for this safe terminal case while
        # requiring plans for every actual instruction.
        if task.instruction.strip().casefold() != "do nothing":
            raise APIError("plan_required", "Generate and approve a plan before execution.", 409)
        result = {"deterministic": True}
        task.status = "completed"
    result.update({"workerId": worker_id, "instruction": task.instruction})
    task.result = result
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


def retry_task(task):
    if task.status not in {"failed", "cancelled"}:
        raise APIError("task_not_retryable", "Only failed or cancelled tasks can be retried.", 409)
    task.status = "pending"
    task.error = None
    task.worker_id = None
    task.lease_expires_at = None
    # A retry must re-enter the planning loop. Do not execute stale failed
    # observations or a terminal plan on the next claim.
    result = dict(task.result or {}) if isinstance(task.result, dict) else {}
    result.pop("plan", None)
    result.pop("observation", None)
    task.result = result
    task.updated_at = utcnow()
    record_event(task, "retry_requested")
    db.session.commit()
    return task

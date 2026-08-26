from app.extensions import db
from app.security.errors import APIError
from app.services.tasks import owned_task
from app.services.verification import _fallback_plan
import re


def generate_plan(task, user_id):
    """Create a conservative, inspectable plan without executing side effects."""
    if task.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this task.", 403)
    if task.status in {"completed", "failed", "cancelled"}:
        raise APIError("task_unavailable", "Terminal tasks cannot be replanned.", 409)
    selected = _fallback_plan(task.instruction)
    expression = task.instruction.strip().replace(",", ".")
    if re.fullmatch(r"[\d\s+\-*/().%^]+", expression):
        selected = selected.__class__("calculate", query=expression, reason="Arithmetic capability selected from the task input")
    plan = {
        "version": 1,
        "status": "proposed",
        "tool": selected.tool,
        "operation": selected.operation,
        "reason": selected.reason,
        "steps": [
            {"id": "understand", "action": "analyze_instruction", "status": "pending"},
            {"id": "capabilities", "action": "analyze_capabilities", "status": "pending"},
            {"id": "risk", "action": "assess_risk_and_permissions", "status": "pending"},
            {"id": "select", "action": "select_tools", "tool": selected.tool, "status": "pending"},
            {"id": "execute", "action": "execute_with_observation", "status": "pending"},
            {"id": "validate", "action": "validate_result", "status": "pending"},
        ],
        "requiresApproval": True,
        "sideEffects": False,
    }
    result = dict(task.result or {}) if isinstance(task.result, dict) else {}
    result["plan"] = plan
    task.result = result
    task.updated_at = __import__("app.models", fromlist=["utcnow"]).utcnow()
    db.session.commit()
    return task


def approve_plan(task, user_id):
    if task.user_id != user_id:
        raise APIError("forbidden", "You do not have access to this task.", 403)
    plan = (task.result or {}).get("plan")
    if not plan:
        raise APIError("plan_required", "Generate a plan before approving it.", 409)
    if task.status in {"completed", "failed", "cancelled"}:
        raise APIError("task_unavailable", "Terminal tasks cannot be approved.", 409)
    plan = dict(plan)
    plan["status"] = "approved"
    plan["requiresApproval"] = False
    plan["steps"] = [dict(step) for step in plan.get("steps", [])]
    result = dict(task.result or {}) if isinstance(task.result, dict) else {}
    result["plan"] = plan
    task.result = result
    task.updated_at = __import__("app.models", fromlist=["utcnow"]).utcnow()
    db.session.commit()
    return task

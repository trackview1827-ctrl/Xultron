from datetime import timedelta

from tests.conftest import patch_json, post_json
from app.extensions import db
from app.models import Task, utcnow
from app.services.tasks import recover_expired_tasks


def test_tasks_are_persistent_and_owned(user_client):
    created = post_json(user_client, "/api/v1/tasks", {"title": "Plan", "instruction": "Review the inbox"})
    assert created.status_code == 201
    task = created.get_json()["task"]
    assert task["status"] == "pending"
    task_id = task["id"]
    updated = patch_json(user_client, f"/api/v1/tasks/{task_id}", {"status": "completed", "result": {"count": 2}})
    assert updated.get_json()["task"]["result"] == {"count": 2}
    assert user_client.get("/api/v1/tasks").get_json()["tasks"][0]["status"] == "completed"
    assert user_client.get(f"/api/v1/tasks/{task_id}").status_code == 200


def test_tasks_validate_input(user_client):
    assert post_json(user_client, "/api/v1/tasks", {"title": "x"}).status_code == 422
    task = post_json(user_client, "/api/v1/tasks", {"title": "x", "instruction": "do"}).get_json()["task"]
    assert patch_json(user_client, f"/api/v1/tasks/{task['id']}", {"status": "bogus"}).status_code == 422


def test_claim_is_idempotent_and_execute_is_deterministic(user_client):
    task = post_json(user_client, "/api/v1/tasks", {"title": "Plan", "instruction": "do nothing"}).get_json()["task"]
    first = post_json(user_client, f"/api/v1/tasks/{task['id']}/claim", {"workerId": "worker-a"}).get_json()["task"]
    second = post_json(user_client, f"/api/v1/tasks/{task['id']}/claim", {"workerId": "worker-a"}).get_json()["task"]
    assert first["status"] == second["status"] == "running"
    assert first["workerId"] == second["workerId"] == "worker-a"
    done = post_json(user_client, f"/api/v1/tasks/{task['id']}/execute", {"workerId": "worker-a"})
    assert done.status_code == 200
    assert done.get_json()["task"]["result"] == {"workerId": "worker-a", "instruction": "do nothing", "deterministic": True}
    assert post_json(user_client, f"/api/v1/tasks/{task['id']}/execute", {"workerId": "worker-a"}).status_code == 409


def test_claim_rejects_other_worker_and_recovers_expired_lease(user_client, app):
    task = post_json(user_client, "/api/v1/tasks", {"title": "Plan", "instruction": "recover"}).get_json()["task"]
    post_json(user_client, f"/api/v1/tasks/{task['id']}/claim", {"workerId": "worker-a"})
    assert post_json(user_client, f"/api/v1/tasks/{task['id']}/claim", {"workerId": "worker-b"}).status_code == 409
    with app.app_context():
        row = db.session.get(Task, task["id"])
        row.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
        assert [x.id for x in recover_expired_tasks()] == [task["id"]]
        assert row.status == "pending" and row.worker_id is None


def test_lease_can_be_renewed_only_by_current_worker(user_client):
    task = post_json(user_client, "/api/v1/tasks", {"title": "Plan", "instruction": "renew"}).get_json()["task"]
    post_json(user_client, f"/api/v1/tasks/{task['id']}/claim", {"workerId": "worker-a"})
    renewed = post_json(user_client, f"/api/v1/tasks/{task['id']}/renew", {"workerId": "worker-a", "leaseSeconds": 120})
    assert renewed.status_code == 200
    assert renewed.get_json()["task"]["workerId"] == "worker-a"
    assert any(event["type"] == "lease_renewed" for event in renewed.get_json()["task"]["result"]["events"])
    assert post_json(user_client, f"/api/v1/tasks/{task['id']}/renew", {"workerId": "worker-b"}).status_code == 409
    assert post_json(user_client, f"/api/v1/tasks/{task['id']}/renew", {"workerId": "worker-a", "leaseSeconds": 3601}).status_code == 422

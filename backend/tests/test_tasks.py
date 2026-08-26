from tests.conftest import patch_json, post_json


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

from tests.conftest import post_json


def test_plan_selects_registered_tool_and_execution_records_observation(user_client):
    task = post_json(user_client, "/api/v1/tasks", {"title": "Calculate", "instruction": "2 + 3"}).get_json()["task"]
    planned = post_json(user_client, f"/api/v1/tasks/{task['id']}/plan", {}).get_json()["task"]
    assert planned["result"]["plan"]["tool"] == "calculate"
    post_json(user_client, f"/api/v1/tasks/{task['id']}/plan/approve", {})
    post_json(user_client, f"/api/v1/tasks/{task['id']}/claim", {"workerId": "worker-a"})
    done = post_json(user_client, f"/api/v1/tasks/{task['id']}/execute", {"workerId": "worker-a"})
    assert done.status_code == 200
    result = done.get_json()["task"]["result"]
    assert result["observation"]["verified"] is True
    assert "2 + 3 = 5" in result["observation"]["evidence"]
    assert any(event["type"] == "observation_recorded" for event in result["events"])


def test_unplanned_execution_cannot_claim_success(user_client):
    task = post_json(user_client, "/api/v1/tasks", {"title": "Unsafe", "instruction": "do something"}).get_json()["task"]
    post_json(user_client, f"/api/v1/tasks/{task['id']}/claim", {"workerId": "worker-a"})
    response = post_json(user_client, f"/api/v1/tasks/{task['id']}/execute", {"workerId": "worker-a"})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "plan_required"

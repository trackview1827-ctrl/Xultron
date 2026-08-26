from app.agent.registry import ToolRegistry, ToolSpec
from app.services.verification import VerificationPlan, _verification_registry, execute


def test_registry_exposes_metadata_for_read_only_capabilities(app):
    with app.app_context():
        descriptions = {item["name"]: item for item in _verification_registry().describe()}

    assert {"runtime", "termux", "project", "web", "calculate", "reasoning"} <= descriptions.keys()
    assert all(item["sideEffect"] is False for item in descriptions.values())
    assert all(item["verificationStrategy"] for item in descriptions.values())


def test_registry_rejects_side_effects_without_explicit_permission():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="mail.send",
        description="Send an email",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        side_effect=True,
        risk_level="high",
        handler=lambda payload: {"sent": True},
    ))

    try:
        registry.execute("mail.send", {})
    except PermissionError as exc:
        assert "explicit permission" in str(exc)
    else:
        raise AssertionError("side-effecting tools must require explicit permission")


def test_verification_dispatches_through_registered_calculator(app):
    with app.app_context():
        result = execute(VerificationPlan("calculate", query="2 + 2"), "2 + 2")

    assert result.verified is True
    assert result.tool == "calculate"
    assert result.evidence == "2 + 2 = 4"


def test_authenticated_tools_endpoint_returns_metadata_without_handlers(user_client):
    response = user_client.get("/api/v1/tools")

    assert response.status_code == 200
    tools = response.get_json()["tools"]
    assert any(tool["name"] == "termux" for tool in tools)
    assert all("handler" not in tool for tool in tools)
    assert all("api_key" not in str(tool).lower() for tool in tools)

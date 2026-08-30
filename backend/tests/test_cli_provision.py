import json

import pytest

from app.extensions import db
from app.models import DEFAULT_SETTINGS, User, UserSettings
from tests.conftest import post_json


def invoke_provision(app, credentials):
    input_text = credentials if isinstance(credentials, str) else json.dumps(credentials)
    return app.test_cli_runner().invoke(args=["provision-first-user"], input=input_text)


def invoke_local_account(app, payload):
    return app.test_cli_runner().invoke(
        args=["provision-local-account"],
        input=json.dumps(payload),
    )


def test_provision_first_user_success_creates_settings_and_supports_web_login(app):
    password = "correct horse battery staple"
    result = invoke_provision(
        app,
        {"username": "  First.User  ", "password": password, "email": None},
    )

    assert result.exit_code == 0, result.output
    assert result.output == "First user provisioned.\n"
    assert password not in result.output
    with app.app_context():
        users = User.query.filter_by(is_guest=False).all()
        assert len(users) == 1
        user = users[0]
        assert user.username == "first.user"
        assert user.email is None
        assert user.password_hash != password
        assert user.check_password(password)
        assert user.settings is not None
        assert user.settings.to_public() == DEFAULT_SETTINGS

    client = app.test_client()
    login = post_json(
        client,
        "/api/v1/auth/login",
        {"identifier": "FIRST.USER", "password": password},
    )
    assert login.status_code == 200, login.get_data(as_text=True)
    assert login.get_json()["user"]["username"] == "first.user"


def test_provision_first_user_refuses_existing_user_without_resetting_password(app):
    old_password = "existing-password"
    new_password = "replacement-password"
    with app.app_context():
        existing = User(username="existing", email="existing@example.com", is_guest=False)
        existing.settings = UserSettings()
        existing.set_password(old_password)
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id
        original_hash = existing.password_hash

    result = invoke_provision(
        app,
        {"username": "new-user", "password": new_password, "email": "new@example.com"},
    )

    assert result.exit_code != 0
    assert "A non-guest user already exists" in result.output
    assert old_password not in result.output
    assert new_password not in result.output
    with app.app_context():
        users = User.query.filter_by(is_guest=False).all()
        assert len(users) == 1
        assert users[0].id == existing_id
        assert users[0].password_hash == original_hash
        assert users[0].check_password(old_password)
        assert not users[0].check_password(new_password)


@pytest.mark.parametrize(
    ("credentials", "message"),
    [
        ("", "Expected a JSON object on stdin"),
        ("not-json", "Invalid JSON on stdin"),
        ([], "credentials must be an object"),
        ({"username": "x", "password": "long-enough-password"}, "Username must be"),
        ({"username": "valid-user", "password": "too-short"}, "at least 10 characters"),
        ({"username": "valid-user", "password": 1234567890}, "password must be a string"),
        (
            {"username": "valid-user", "password": "long-enough-password", "email": "bad"},
            "A valid email is required",
        ),
        (
            {"username": "valid-user", "password": "x" * 1025},
            "password is too long",
        ),
    ],
)
def test_provision_first_user_rejects_invalid_input(app, credentials, message):
    result = invoke_provision(app, credentials)

    assert result.exit_code != 0
    assert message in result.output
    with app.app_context():
        assert User.query.count() == 0


def test_guest_user_does_not_block_first_non_guest_provisioning(app):
    with app.app_context():
        guest = User(username="guest_existing", is_guest=True)
        guest.settings = UserSettings()
        db.session.add(guest)
        db.session.commit()

    result = invoke_provision(
        app,
        {"username": "owner", "password": "owner-password"},
    )

    assert result.exit_code == 0, result.output
    with app.app_context():
        assert User.query.filter_by(is_guest=True).count() == 1
        assert User.query.filter_by(is_guest=False).count() == 1


def test_local_account_contract_reports_status_then_creates_once(app):
    status = invoke_local_account(app, {"action": "status"})
    assert status.exit_code == 0, status.output
    assert json.loads(status.output) == {"accountExists": False}

    created = invoke_local_account(
        app,
        {"action": "create", "username": "operator", "password": "operator-password"},
    )
    assert created.exit_code == 0, created.output
    assert json.loads(created.output) == {"created": True, "username": "operator"}

    status = invoke_local_account(app, {"action": "status"})
    assert status.exit_code == 0, status.output
    assert json.loads(status.output) == {"accountExists": True}

    duplicate = invoke_local_account(
        app,
        {"action": "create", "username": "other", "password": "other-password"},
    )
    assert duplicate.exit_code != 0
    assert "already exists" in duplicate.output

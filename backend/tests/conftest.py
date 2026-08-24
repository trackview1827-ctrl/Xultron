import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user_client(app):
    c = app.test_client()
    register(c, "alice", "alice@example.com", "password123")
    return c


def csrf(client):
    rv = client.get("/api/v1/auth/session")
    assert rv.status_code == 200, rv.get_data(as_text=True)
    return rv.get_json()["csrfToken"]


def post_json(client, path, body, token=None, **headers):
    token = token or csrf(client)
    return client.post(path, json=body, headers={"X-CSRF-Token": token, **headers})


def patch_json(client, path, body, token=None, **headers):
    token = token or csrf(client)
    return client.patch(path, json=body, headers={"X-CSRF-Token": token, **headers})


def delete_json(client, path, body=None, token=None, **headers):
    token = token or csrf(client)
    kwargs = {"headers": {"X-CSRF-Token": token, **headers}}
    if body is not None:
        kwargs["json"] = body
    return client.delete(path, **kwargs)


def register(client, username, email, password):
    rv = post_json(client, "/api/v1/auth/register", {"username": username, "email": email, "password": password})
    assert rv.status_code == 201, rv.get_data(as_text=True)
    return rv.get_json()["user"]


def guest(client):
    rv = post_json(client, "/api/v1/auth/guest", {})
    assert rv.status_code == 201, rv.get_data(as_text=True)
    return rv.get_json()["user"]

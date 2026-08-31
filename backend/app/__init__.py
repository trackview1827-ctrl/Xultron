import json
import logging
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, abort, send_from_directory

from app.api import api_bp
from app.auth import device_auth_bp
from app.config import Config
from app.devices import device_api_bp
from app.extensions import db, install_sqlite_pragmas, migrate
from app.security.errors import register_error_handlers
from app.security.guards import install_guards
from app.security.redaction import RedactingFilter


def create_app(config_object=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    cfg = config_object or Config
    app.config.from_object(cfg)
    cfg.validate()
    app.instance_path and __import__("os").makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    install_sqlite_pragmas(app)
    migrate.init_app(app, db)
    app.logger.addFilter(RedactingFilter())
    logging.getLogger("werkzeug").addFilter(RedactingFilter())

    install_guards(app)
    register_error_handlers(app)
    app.register_blueprint(api_bp)
    app.register_blueprint(device_auth_bp)
    app.register_blueprint(device_api_bp)

    dist_dir = Path(app.config["FRONTEND_DIST_DIR"])

    @app.get("/assets/<path:filename>")
    def frontend_assets(filename):
        if not dist_dir.exists():
            abort(404)
        response = send_from_directory(dist_dir / "assets", filename)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.get("/")
    @app.get("/<path:path>")
    def frontend_spa(path=""):
        if path.startswith("api/"):
            abort(404)
        if not dist_dir.exists():
            abort(404)
        requested = dist_dir / path
        if path and requested.is_file():
            response = send_from_directory(dist_dir, path)
            response.headers["Cache-Control"] = "no-cache, max-age=0" if path == "sw.js" else "public, max-age=3600"
            return response
        response = send_from_directory(dist_dir, "index.html")
        response.headers["Cache-Control"] = "no-cache, max-age=0"
        return response

    @app.cli.command("cleanup-expired")
    def cleanup_expired_root():
        from app.services.auth import cleanup_expired
        print(cleanup_expired())

    @app.cli.command("provision-local-pin")
    def provision_local_pin_root():
        """Create or reset the configured local PIN identity from its stored hash."""
        from app.services.auth import provision_local_pin_user
        user = provision_local_pin_user(force=True)
        print(f"Local PIN identity ready: {user.username}")

    def read_local_account_request():
        """Read one bounded JSON object from stdin without exposing credentials."""
        from app.security.errors import APIError

        raw = click.get_text_stream("stdin").read(16_385)
        if not raw.strip():
            raise click.ClickException(
                "Expected a JSON object on stdin with username, password, and optional email."
            )
        if len(raw) > 16_384:
            raise click.ClickException("JSON input is too large.")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise click.ClickException(
                f"Invalid JSON on stdin at line {error.lineno}, column {error.colno}."
            ) from None
        if not isinstance(payload, dict):
            raise click.ClickException("credentials must be an object.")
        return payload, APIError

    @app.cli.command("provision-first-user")
    def provision_first_user_root():
        """Create the first non-guest user from JSON credentials read on stdin."""
        from app.services.auth import provision_first_user

        credentials, api_error = read_local_account_request()
        try:
            provision_first_user(credentials)
        except api_error as error:
            raise click.ClickException(error.message) from None
        click.echo("First user provisioned.")

    @app.cli.command("provision-local-account")
    def provision_local_account_root():
        """Report or create the installation's first local account via stdin JSON."""
        from app.models import User
        from app.services.auth import provision_first_user

        payload, api_error = read_local_account_request()
        action = payload.pop("action", None)
        if action == "status":
            exists = User.query.filter_by(is_guest=False).first() is not None
            click.echo(json.dumps({"accountExists": exists}, separators=(",", ":")))
            return
        if action != "create":
            raise click.ClickException("action must be status or create.")
        try:
            user = provision_first_user(payload)
        except api_error as error:
            raise click.ClickException(error.message) from None
        click.echo(json.dumps({"created": True, "username": user.username}, separators=(",", ":")))

    return app

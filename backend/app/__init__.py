import logging
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, send_from_directory

from app.api import api_bp
from app.config import Config
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

    return app

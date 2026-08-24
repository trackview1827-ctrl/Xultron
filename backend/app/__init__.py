import logging
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, send_from_directory

from app.api import api_bp
from app.config import Config
from app.extensions import db, migrate
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
    migrate.init_app(app, db)
    app.logger.addFilter(RedactingFilter())
    logging.getLogger("werkzeug").addFilter(RedactingFilter())

    install_guards(app)
    register_error_handlers(app)
    app.register_blueprint(api_bp)

    dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"

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
        if not dist_dir.exists():
            abort(404)
        requested = dist_dir / path
        if path and requested.is_file():
            response = send_from_directory(dist_dir, path)
            response.headers["Cache-Control"] = "public, max-age=3600"
            return response
        response = send_from_directory(dist_dir, "index.html")
        response.headers["Cache-Control"] = "no-cache, max-age=0"
        return response

    @app.cli.command("cleanup-expired")
    def cleanup_expired_root():
        from app.services.auth import cleanup_expired
        print(cleanup_expired())

    return app

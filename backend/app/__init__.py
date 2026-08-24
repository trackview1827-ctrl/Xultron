import logging

from dotenv import load_dotenv
from flask import Flask

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

    @app.cli.command("cleanup-expired")
    def cleanup_expired_root():
        from app.services.auth import cleanup_expired
        print(cleanup_expired())

    return app

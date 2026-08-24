import uuid
from flask import jsonify, request
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        super().__init__(message)


def error_response(code: str, message: str, status: int, retryable: bool = False):
    request_id = getattr(request, "request_id", None) or f"req_{uuid.uuid4().hex}"
    return jsonify({"error": {"code": code, "message": message, "retryable": retryable, "requestId": request_id}}), status


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def api_error(err):
        return error_response(err.code, err.message, err.status, err.retryable)

    @app.errorhandler(HTTPException)
    def http_error(err):
        code = "request_entity_too_large" if err.code == 413 else "http_error"
        message = "Request is too large." if err.code == 413 else "Request failed."
        return error_response(code, message, err.code or 500)

    @app.errorhandler(Exception)
    def unhandled(err):
        app.logger.error(
            "Unhandled API error type=%s request_id=%s",
            type(err).__name__,
            getattr(request, "request_id", "unknown"),
        )
        return error_response("internal_error", "An internal error occurred.", 500)

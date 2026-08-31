from flask import Blueprint, jsonify

from app.security.guards import require_json, require_mobile_principal
from app.services.device_auth import register_current_device

device_api_bp = Blueprint("device_api", __name__, url_prefix="/api/v1/devices")


@device_api_bp.post("/register")
def register():
    device = register_current_device(require_json(), require_mobile_principal())
    return jsonify({"device": device.to_public()}), 200

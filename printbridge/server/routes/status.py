"""Status endpoint."""

from flask import Blueprint, current_app, jsonify

bp = Blueprint("status", __name__)


@bp.route("/api/status", methods=["GET"])
def status():
    """Health check — web app uses this to detect if the agent is running."""
    config = current_app.config["PRINTBRIDGE_CONFIG"]
    return jsonify({
        "status": "ok",
        "version": current_app.config["PRINTBRIDGE_VERSION"],
        "platform": current_app.config["PRINTBRIDGE_PLATFORM"],
        "port": config.port,
        "tspl": True,
    })

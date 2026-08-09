"""Printers endpoint."""

from flask import Blueprint, current_app, jsonify

bp = Blueprint("printers", __name__)


@bp.route("/api/printers", methods=["GET"])
def list_printers():
    """List available printers."""
    backend = current_app.config["PRINTBRIDGE_BACKEND"]
    printers = backend.list_printers()
    default = backend.get_default_printer()
    return jsonify({
        "printers": printers,
        "default": default,
    })

"""PDF printing endpoint."""

import base64
import logging

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("pdf", __name__)
logger = logging.getLogger("printbridge")


@bp.route("/api/print", methods=["POST"])
def print_pdf():
    """Print a base64-encoded PDF silently."""
    try:
        data = request.get_json()
        if not data or "pdf" not in data:
            return jsonify({"error": 'Missing "pdf" field (base64-encoded PDF)'}), 400

        pdf_base64 = data["pdf"]
        printer_name = data.get("printer", None)
        copies = int(data.get("copies", 1))
        media_width = data.get("mediaWidth", None)
        media_height = data.get("mediaHeight", None)

        if copies < 1 or copies > 99:
            return jsonify({"error": "Copies must be between 1 and 99"}), 400

        try:
            pdf_bytes = base64.b64decode(pdf_base64)
        except Exception:
            return jsonify({"error": "Invalid base64 data"}), 400

        if not pdf_bytes[:5] == b"%PDF-":
            return jsonify({"error": "Data is not a valid PDF"}), 400

        backend = current_app.config["PRINTBRIDGE_BACKEND"]
        backend.print_pdf(pdf_bytes, printer_name, copies, media_width, media_height)

        return jsonify({
            "success": True,
            "printer": printer_name or backend.get_default_printer(),
            "copies": copies,
        })

    except Exception as e:
        logger.error(f"Print route error: {e}")
        return jsonify({"error": str(e)}), 500

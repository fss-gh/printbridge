"""TSPL test and raw printing endpoints."""

import logging

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("tspl", __name__)
logger = logging.getLogger("printbridge")


@bp.route("/api/test-tspl", methods=["POST"])
def test_tspl():
    """Send a test TSPL label to verify printer connectivity."""
    try:
        data = request.get_json() or {}
        printer_name = data.get("printer", None)
        label_width = int(data.get("labelWidth", 100))
        label_height = int(data.get("labelHeight", 150))

        config = current_app.config["PRINTBRIDGE_CONFIG"]

        test_tspl = (
            f"SIZE {label_width} mm, {label_height} mm\r\n"
            "GAP 2 mm, 0 mm\r\n"
            "DIRECTION 1\r\n"
            "CLS\r\n"
            'TEXT 50,30,"4",0,1,1,"PrintBridge Test"\r\n'
            'TEXT 50,80,"3",0,1,1,"Label Printing Works"\r\n'
            f"BAR 30,120,740,2\r\n"
            f'TEXT 50,140,"4",0,1,1,"Size: {label_width}x{label_height}mm"\r\n'
            'TEXT 50,200,"3",0,1,1,"Scan QR to verify"\r\n'
            f'QRCODE 520,200,M,6,A,0,"https://github.com/AnouarSbia/printbridge"\r\n'
            f"BAR 30,300,740,2\r\n"
            f'TEXT 50,320,"3",0,1,1,"{config.footer_text}"\r\n'
            "PRINT 1,1\r\n"
        )

        logger.info(f"TEST TSPL: sending test label ({len(test_tspl)} bytes)")
        backend = current_app.config["PRINTBRIDGE_BACKEND"]
        backend.send_raw(test_tspl, printer_name)

        return jsonify({"success": True, "method": "test", "bytes": len(test_tspl)})
    except Exception as e:
        logger.error(f"Test TSPL error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/print-tspl", methods=["POST"])
def print_tspl():
    """Send raw TSPL commands to a printer."""
    try:
        data = request.get_json() or {}
        printer_name = data.get("printer", None)

        tspl_commands = data.get("commands", "")
        if not tspl_commands:
            return jsonify({"error": 'Missing "commands" field'}), 400

        if isinstance(tspl_commands, list):
            tspl_commands = "\r\n".join(tspl_commands)

        backend = current_app.config["PRINTBRIDGE_BACKEND"]
        backend.send_raw(tspl_commands, printer_name)

        return jsonify({
            "success": True,
            "printer": printer_name or backend.get_default_printer(),
            "bytes": len(tspl_commands),
        })
    except Exception as e:
        logger.error(f"Print TSPL error: {e}")
        return jsonify({"error": str(e)}), 500

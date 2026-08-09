"""Custom exceptions for PrintBridge API."""


class PrintBridgeError(Exception):
    """Base exception for all PrintBridge errors."""

    status_code = 500


class InvalidPDFError(PrintBridgeError):
    status_code = 400


class InvalidBase64Error(PrintBridgeError):
    status_code = 400


class InvalidLabelDataError(PrintBridgeError):
    status_code = 400


class PrinterNotFoundError(PrintBridgeError):
    status_code = 404


class PrintJobFailedError(PrintBridgeError):
    status_code = 500


def register_error_handlers(app) -> None:
    """Register error handlers for PrintBridge exceptions on a Flask app."""

    from flask import jsonify

    @app.errorhandler(PrintBridgeError)
    def handle_printbridge_error(e: PrintBridgeError):
        return jsonify({"error": str(e)}), e.status_code

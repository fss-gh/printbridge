"""Flask app factory."""

import platform

from flask import Flask, jsonify
from flask_cors import CORS

from ..config import PrintBridgeConfig
from ..printers.base import PrinterBackend
from .errors import register_error_handlers


def create_app(config: PrintBridgeConfig, printer_backend: PrinterBackend) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: PrintBridge configuration.
        printer_backend: Platform-specific printer backend.

    Returns:
        Configured Flask app with all routes registered.
    """
    app = Flask(__name__)
    CORS(app, origins=config.cors_origins)

    # Store backend and config on app for route access
    app.config["PRINTBRIDGE_CONFIG"] = config
    app.config["PRINTBRIDGE_BACKEND"] = printer_backend
    app.config["PRINTBRIDGE_VERSION"] = "1.0.0"
    app.config["PRINTBRIDGE_PLATFORM"] = platform.system()

    # Register blueprints
    from .routes.status import bp as status_bp
    from .routes.printers import bp as printers_bp
    from .routes.pdf import bp as pdf_bp
    from .routes.labels import bp as labels_bp
    from .routes.tspl import bp as tspl_bp

    app.register_blueprint(status_bp)
    app.register_blueprint(printers_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(labels_bp)
    app.register_blueprint(tspl_bp)

    register_error_handlers(app)

    return app

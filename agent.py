"""
PrintBridge — Silent Local Printing Service

A lightweight local print agent that runs in the system tray.
Any web application can send print jobs via HTTP to localhost,
and this agent prints them silently to the selected printer.

Supports:
  - Silent PDF printing (any system printer)
  - TSPL label printing (thermal printers: TSC, Xprinter, etc.)
  - QR codes, barcode support
  - Unicode/Arabic text rendering via bitmap
  - Custom label templates

Works on macOS, Windows, and Linux.

Configuration: see config.json (or environment variables).
"""

import logging
import sys
import threading

from printbridge.config import PrintBridgeConfig
from printbridge.logging_setup import setup_logging
from printbridge.platform.autostart import install_autostart
from printbridge.platform.single_instance import ensure_single_instance
from printbridge.printers.factory import get_printer_backend
from printbridge.server.app import create_app
from printbridge.tray.icon import run_tray


def keep_alive(logger: logging.Logger) -> None:
    """Keep the process alive if tray icon exits or isn't available."""
    import time

    logger.info("Running in headless mode (no tray icon)")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)


def main() -> None:
    """Entry point for PrintBridge agent."""
    # Load configuration
    config = PrintBridgeConfig.load()

    # Set up logging
    logger = setup_logging(config.log_path)

    # Prevent multiple instances
    ensure_single_instance(config.log_path)

    # Auto-register for startup
    install_autostart()

    # Get platform-specific printer backend
    printer_backend = get_printer_backend()

    # Create Flask app
    app = create_app(config, printer_backend)

    # Start Flask server in background thread
    def run_server():
        logger.info(f"Starting PrintBridge v1.0.0 on port {config.port}")
        logger.info(f"Platform: {sys.platform}")
        logger.info(f"Printers: {printer_backend.list_printers()}")
        app.run(
            host="127.0.0.1",
            port=config.port,
            debug=False,
            use_reloader=False,
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Try running tray icon in main thread (required by macOS AppKit)
    run_tray(config, printer_backend)

    # If tray exited, keep the process alive
    keep_alive(logger)


if __name__ == "__main__":
    main()

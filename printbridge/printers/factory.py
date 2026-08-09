"""Printer backend factory."""

import platform

from .base import PrinterBackend


def get_printer_backend() -> PrinterBackend:
    """Return the appropriate printer backend for the current platform."""
    system = platform.system()

    if system in ("Darwin", "Linux"):
        from .cups import CupsBackend

        return CupsBackend()
    elif system == "Windows":
        from .windows import WindowsBackend

        return WindowsBackend()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

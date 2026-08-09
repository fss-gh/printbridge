"""System tray icon setup and menu construction."""

import logging
import os
import subprocess
import sys
import threading

from ..config import PrintBridgeConfig
from ..printers.base import PrinterBackend

logger = logging.getLogger("printbridge")


def get_icon_path() -> str:
    """Get the path to the tray icon."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "icon.png")


def run_tray(config: PrintBridgeConfig, printer_backend: PrinterBackend) -> None:
    """Run the system tray icon (blocking).

    Args:
        config: PrintBridge configuration.
        printer_backend: Printer backend for listing printers.
    """
    try:
        import pystray
        from PIL import Image, ImageDraw

        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            image = Image.open(icon_path)
        else:
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse([4, 4, 60, 60], fill=(48, 86, 211, 255))

        def on_quit(icon, item):
            icon.stop()
            os._exit(0)

        def on_open_log(icon, item):
            log_file = str(config.log_path / "agent.log")
            if sys.platform == "darwin":
                subprocess.Popen(["open", log_file])
            elif sys.platform == "win32":
                os.startfile(log_file)  # type: ignore
            else:
                subprocess.Popen(["xdg-open", log_file])

        printer_list = printer_backend.list_printers()
        printer_count = len(printer_list)
        tray_name = config.tray_name

        menu = pystray.Menu(
            pystray.MenuItem(f"{tray_name} v{config.port and '1.0.0'}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("● Running", None, enabled=False),
            pystray.MenuItem(
                f"{printer_count} printer{'s' if printer_count != 1 else ''} detected",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Printers",
                pystray.Menu(
                    *[pystray.MenuItem(p, None, enabled=False) for p in printer_list]
                    or [pystray.MenuItem("No printers found", None, enabled=False)]
                ),
            ),
            pystray.MenuItem(f"Port: {config.port}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("View logs", on_open_log),
            pystray.MenuItem("Quit", on_quit),
        )

        tooltip = f"{tray_name} — Running ({printer_count} printer{'s' if printer_count != 1 else ''})"
        icon = pystray.Icon("printbridge", image, tooltip, menu)
        logger.info("System tray icon started")

        def on_setup(icon):
            icon.visible = True

            def _notify():
                import time

                time.sleep(2)
                try:
                    icon.notify(
                        f"Agent ready — {printer_count} printer{'s' if printer_count != 1 else ''} detected (port {config.port})",
                        tray_name,
                    )
                except Exception:
                    pass

            threading.Thread(target=_notify, daemon=True).start()

        icon.run(setup=on_setup)

    except Exception as e:
        logger.warning(f"System tray not available: {e}")
        return

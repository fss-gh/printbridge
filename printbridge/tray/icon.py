"""System tray icon setup and menu construction."""

import logging
import os
import subprocess
import sys
import threading

from ..config import PrintBridgeConfig
from ..printers.base import PrinterBackend

logger = logging.getLogger("printbridge")

TRANSLATIONS = {
    "zh": {
        "running": "● 运行中",
        "printers_detected": "检测到 {count} 台打印机",
        "printers": "打印机",
        "no_printers": "未找到打印机",
        "port": "端口：{port}",
        "view_logs": "查看日志",
        "view_agent_log": "主程序日志",
        "view_tcp2ws_log": "tcp2ws 日志",
        "quit": "退出",
        "language": "语言",
        "language_zh": "中文",
        "language_en": "English",
        "tooltip": "{tray_name} — 运行中（{count} 台打印机）",
        "notify_ready": "代理已就绪 — 检测到 {count} 台打印机（端口 {port}）",
    },
    "en": {
        "running": "● Running",
        "printers_detected": "{count} printer(s) detected",
        "printers": "Printers",
        "no_printers": "No printers found",
        "port": "Port: {port}",
        "view_logs": "View logs",
        "view_agent_log": "Main program log",
        "view_tcp2ws_log": "tcp2ws log",
        "quit": "Quit",
        "language": "Language",
        "language_zh": "中文",
        "language_en": "English",
        "tooltip": "{tray_name} — Running ({count} printer(s))",
        "notify_ready": "Agent ready — {count} printer(s) detected (port {port})",
    },
}


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

        def _open_path(path):
            if not path.exists():
                path = path.parent
            target = str(path)
            if sys.platform == "darwin":
                subprocess.Popen(["open", target])
            elif sys.platform == "win32":
                os.startfile(target)  # type: ignore
            else:
                subprocess.Popen(["xdg-open", target])

        def on_open_log(icon, item):
            _open_path(config.log_path / "agent.log")

        def on_open_tcp2ws_log(icon, item):
            _open_path(config.log_path / "tcp2ws.log")

        printer_list = printer_backend.list_printers()
        printer_count = len(printer_list)
        tray_name = config.tray_name

        # Current UI language. Can be changed from the tray menu and is
        # persisted to config.json so it survives restarts.
        state = {
            "language": config.language if config.language in TRANSLATIONS else "zh"
        }

        def _tr(key: str, **kwargs) -> str:
            """Translate a key using the current language."""
            return TRANSLATIONS[state["language"]][key].format(**kwargs)

        def _build_menu():
            return pystray.Menu(
                pystray.MenuItem(f"{tray_name} v{config.port and '1.0.0'}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(_tr("running"), None, enabled=False),
                pystray.MenuItem(
                    _tr("printers_detected", count=printer_count),
                    None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    _tr("printers"),
                    pystray.Menu(
                        *[pystray.MenuItem(p, None, enabled=False) for p in printer_list]
                        or [pystray.MenuItem(_tr("no_printers"), None, enabled=False)]
                    ),
                ),
                pystray.MenuItem(_tr("port", port=config.port), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    _tr("language"),
                    pystray.Menu(
                        pystray.MenuItem(
                            _tr("language_zh"),
                            lambda icon, item: _set_language(icon, "zh"),
                            checked=lambda item: state["language"] == "zh",
                            radio=True,
                        ),
                        pystray.MenuItem(
                            _tr("language_en"),
                            lambda icon, item: _set_language(icon, "en"),
                            checked=lambda item: state["language"] == "en",
                            radio=True,
                        ),
                    ),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    _tr("view_logs"),
                    pystray.Menu(
                        pystray.MenuItem(_tr("view_agent_log"), on_open_log),
                        pystray.MenuItem(_tr("view_tcp2ws_log"), on_open_tcp2ws_log),
                    ),
                ),
                pystray.MenuItem(_tr("quit"), on_quit),
            )

        def _set_language(icon, language):
            state["language"] = language
            config.language = language
            try:
                config.save()
            except Exception as e:
                logger.warning(f"Failed to save language setting: {e}")
            icon.menu = _build_menu()
            icon.title = _tr("tooltip", tray_name=tray_name, count=printer_count)
            try:
                icon.update_menu()
            except Exception as e:
                logger.warning(f"Failed to update tray menu language: {e}")

        menu = _build_menu()
        tooltip = _tr("tooltip", tray_name=tray_name, count=printer_count)
        icon = pystray.Icon("printbridge", image, tooltip, menu)
        logger.info("System tray icon started")

        def on_setup(icon):
            icon.visible = True

            def _notify():
                import time

                time.sleep(2)
                try:
                    icon.notify(
                        _tr("notify_ready", count=printer_count, port=config.port),
                        tray_name,
                    )
                except Exception:
                    pass

            threading.Thread(target=_notify, daemon=True).start()

        icon.run(setup=on_setup)

    except Exception as e:
        logger.warning(f"System tray not available: {e}")
        return

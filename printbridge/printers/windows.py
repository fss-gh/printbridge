"""Windows printer backend using win32print and CLI PDF printers (SumatraPDF)."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from .base import PrinterBackend

logger = logging.getLogger("printbridge")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _delayed_cleanup(path: str, delay: int = 15) -> None:
    """Delete a temp file after a delay (Windows needs time for async print)."""
    import time

    time.sleep(delay)
    try:
        os.unlink(path)
    except Exception:
        pass


def _bundle_dir() -> str:
    """Return the PyInstaller bundle root when frozen, else the source directory."""
    if hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))


def _find_in_app_paths(executable_name: str) -> str | None:
    """Find an installed executable using Windows App Paths registry keys."""
    try:
        import winreg
    except ImportError:
        return None

    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(
                root,
                rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}",
            ) as key:
                value, _ = winreg.QueryValueEx(key, None)
                if value and os.path.isfile(value):
                    return value
        except OSError:
            continue
    return None


def _find_sumatra() -> str | None:
    """Find SumatraPDF executable on Windows."""
    candidates = [
        # Bundled copy: when frozen by PyInstaller, SumatraPDF.exe is placed at
        # the bundle root (_MEIPASS) via the spec's datas entry.
        os.path.join(_bundle_dir(), "SumatraPDF.exe"),
        # Source checkout: next to this module or in the project root
        # (where PrintBridge.spec expects SumatraPDF.exe to be placed).
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "SumatraPDF.exe"),
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "SumatraPDF.exe",
        ),
    ]
    for env in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"):
        base = os.environ.get(env)
        if base:
            candidates.append(os.path.join(base, "SumatraPDF", "SumatraPDF.exe"))

    for path in candidates:
        if path and os.path.isfile(path):
            return path

    app_path = _find_in_app_paths("SumatraPDF.exe")
    if app_path:
        return app_path

    try:
        exe = shutil.which("SumatraPDF.exe")
        if exe:
            return exe
    except Exception:
        pass
    return None


def _sumatra_print_settings(
    copies: int,
    media_width: float | None,
    media_height: float | None,
) -> str:
    """Build SumatraPDF -print-settings, including copies and optional paper size."""
    settings = [f"{copies}x"]
    if media_width and media_height:
        try:
            w = float(media_width)
            h = float(media_height)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid mediaWidth/mediaHeight for SumatraPDF print")
            return ",".join(settings)
        settings.append(f"paper={w:g}mm x {h:g}mm")
        settings.append("fit")
    return ",".join(settings)


def _powershell_quote(value: str) -> str:
    """Quote a value for a PowerShell single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


class WindowsBackend(PrinterBackend):
    """Printer backend for Windows using win32print."""

    def list_printers(self) -> list[str]:
        """List available printers via win32print."""
        try:
            import win32print

            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printer_list = win32print.EnumPrinters(flags, None, 2)
            return [p["pPrinterName"] for p in printer_list]
        except Exception as e:
            logger.error(f"Error listing printers: {e}")
            return []

    def get_default_printer(self) -> str | None:
        """Get the default printer via win32print."""
        try:
            import win32print

            return win32print.GetDefaultPrinter()
        except Exception as e:
            logger.error(f"Error getting default printer: {e}")
        return None

    def send_raw(self, data: bytes, printer_name: str | None = None) -> bool:
        """Send raw TSPL commands via win32print."""
        import win32print

        if not printer_name:
            printer_name = win32print.GetDefaultPrinter()
            logger.debug(f"[send_raw] resolved default printer: {printer_name!r}")

        logger.debug(f"[send_raw] opening win32print handle for {printer_name!r}")
        h = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(h, 1, ("TSPL Label", None, "RAW"))
            win32print.StartPagePrinter(h)
            written = win32print.WritePrinter(h, data)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
            logger.info(f"TSPL sent to {printer_name} ({written} bytes written)")
        except Exception as e:
            logger.error(f"win32print error: {e}")
            raise
        finally:
            win32print.ClosePrinter(h)

        return True

    def print_pdf(
        self,
        pdf_bytes: bytes,
        printer_name: str | None = None,
        copies: int = 1,
        media_width: float | None = None,
        media_height: float | None = None,
    ) -> bool:
        """Print a PDF silently.

        Strategy order:
        1. SumatraPDF CLI (bundled with PyInstaller or auto-detected, has error codes)
        2. PowerShell Start-Process -Verb PrintTo (depends on the default PDF viewer)
        3. ShellExecute printto fallback
        """
        import win32api
        import win32print

        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_file.write(pdf_bytes)
        tmp_file.close()
        tmp_path = tmp_file.name

        try:
            target_printer = printer_name or win32print.GetDefaultPrinter()
            printed = False

            # Strategy 1: SumatraPDF CLI
            sumatra = _find_sumatra()
            if sumatra:
                try:
                    cmd = [
                        sumatra,
                        "-print-to", target_printer,
                        "-print-settings", _sumatra_print_settings(copies, media_width, media_height),
                        "-silent",
                        tmp_path,
                    ]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        creationflags=_NO_WINDOW,
                    )
                    if result.returncode == 0:
                        printed = True
                        logger.info(f"Printed {copies} copies to {target_printer} via SumatraPDF")
                    else:
                        logger.warning(f"SumatraPDF failed (code {result.returncode}): {result.stderr}")
                except Exception as e:
                    logger.warning(f"SumatraPDF error: {e}")

            # Strategy 2: PowerShell Start-Process -Verb PrintTo
            if not printed:
                try:
                    ps_cmd = (
                        "$ErrorActionPreference = 'Stop'; "
                        f"Start-Process -FilePath {_powershell_quote(tmp_path)} "
                        f"-Verb PrintTo -ArgumentList {_powershell_quote(f'\"{target_printer}\"')} "
                        "-WindowStyle Hidden -Wait"
                    )
                    for _ in range(copies):
                        result = subprocess.run(
                            ["powershell", "-NoProfile", "-Command", ps_cmd],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            creationflags=_NO_WINDOW,
                        )
                        if result.returncode != 0:
                            raise Exception(f"PowerShell exit {result.returncode}: {result.stderr}")
                    printed = True
                    logger.info(f"Printed {copies} copies to {target_printer} via PowerShell")
                except Exception as e:
                    logger.warning(f"PowerShell print failed: {e}")

            # Strategy 3: ShellExecute printto fallback
            if not printed:
                try:
                    for _ in range(copies):
                        ret = win32api.ShellExecute(
                            0, "printto", tmp_path,
                            f'"{target_printer}"', ".", 0,
                        )
                        # ShellExecute returns <= 32 on failure; it does not raise for
                        # every error, so check the return value explicitly.
                        if ret <= 32:
                            raise Exception(f"ShellExecute printto failed with code {ret}")
                    printed = True
                    logger.info(f"Printed {copies} copies to {target_printer} via ShellExecute")
                except Exception as e:
                    logger.error(f"ShellExecute also failed: {e}")
                    raise Exception(
                        f'All print methods failed for printer "{target_printer}". '
                        f"Install SumatraPDF (https://www.sumatrapdfreader.org/download-free-pdf-viewer) "
                        f"or configure a PDF viewer that supports silent command-line printing. "
                        f"Microsoft Edge does not provide a reliable silent PrintTo interface."
                    ) from e

            cleanup_thread = threading.Thread(
                target=_delayed_cleanup, args=(tmp_path, 30), daemon=True
            )
            cleanup_thread.start()

        except Exception as e:
            logger.error(f"Print failed: {e}")
            raise

        return True

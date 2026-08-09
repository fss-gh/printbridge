"""Windows printer backend using win32print and SumatraPDF."""

import logging
import os
import subprocess
import tempfile
import threading

from .base import PrinterBackend

logger = logging.getLogger("printbridge")


def _delayed_cleanup(path: str, delay: int = 15) -> None:
    """Delete a temp file after a delay (Windows needs time for async print)."""
    import time

    time.sleep(delay)
    try:
        os.unlink(path)
    except Exception:
        pass


def _find_sumatra() -> str | None:
    """Find SumatraPDF executable on Windows."""
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "SumatraPDF.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    try:
        result = subprocess.run(
            ["where", "SumatraPDF.exe"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return None


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
        """Print PDF using SumatraPDF, PowerShell, or ShellExecute fallback."""
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
                        "-print-settings", f"{copies}x",
                        "-silent",
                        tmp_path,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        printed = True
                        logger.info(f"Printed {copies} copies to {target_printer} via SumatraPDF")
                    else:
                        logger.warning(f"SumatraPDF failed (code {result.returncode}): {result.stderr}")
                except Exception as e:
                    logger.warning(f"SumatraPDF error: {e}")

            # Strategy 2: PowerShell
            if not printed:
                try:
                    ps_cmd = (
                        f'Start-Process -FilePath "{tmp_path}" '
                        f'-Verb PrintTo -ArgumentList \'"{target_printer}"\' '
                        f"-WindowStyle Hidden -Wait"
                    )
                    for _ in range(copies):
                        result = subprocess.run(
                            ["powershell", "-NoProfile", "-Command", ps_cmd],
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        if result.returncode != 0:
                            raise Exception(f"PowerShell exit {result.returncode}: {result.stderr}")
                    printed = True
                    logger.info(f"Printed {copies} copies to {target_printer} via PowerShell")
                except Exception as e:
                    logger.warning(f"PowerShell print failed: {e}")

            # Strategy 3: ShellExecute fallback
            if not printed:
                try:
                    for _ in range(copies):
                        win32api.ShellExecute(
                            0, "printto", tmp_path,
                            f'"{target_printer}"', ".", 0,
                        )
                    printed = True
                    logger.info(f"Printed {copies} copies to {target_printer} via ShellExecute")
                except Exception as e:
                    logger.error(f"ShellExecute also failed: {e}")
                    raise Exception(
                        f'All print methods failed for printer "{target_printer}". '
                        f"Please install SumatraPDF for reliable silent printing: "
                        f"https://www.sumatrapdfreader.org/download-free-pdf-viewer"
                    )

            cleanup_thread = threading.Thread(
                target=_delayed_cleanup, args=(tmp_path, 30), daemon=True
            )
            cleanup_thread.start()

        except Exception as e:
            logger.error(f"Print failed: {e}")
            raise

        return True

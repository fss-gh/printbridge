"""macOS/Linux printer backend using CUPS (lp/lpstat/lpr)."""

import logging
import os
import subprocess
import tempfile

from .base import PrinterBackend

logger = logging.getLogger("printbridge")


class CupsBackend(PrinterBackend):
    """Printer backend for macOS and Linux using CUPS commands."""

    def list_printers(self) -> list[str]:
        """List available printers via lpstat."""
        try:
            result = subprocess.run(
                ["lpstat", "-a"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            printers = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line:
                    name = line.split()[0]
                    printers.append(name)
            return printers
        except Exception as e:
            logger.error(f"Error listing printers: {e}")
            return []

    def get_default_printer(self) -> str | None:
        """Get the default printer via lpstat."""
        try:
            result = subprocess.run(
                ["lpstat", "-d"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            parts = result.stdout.strip().split(":")
            if len(parts) >= 2:
                return parts[1].strip()
        except Exception as e:
            logger.error(f"Error getting default printer: {e}")
        return None

    def send_raw(self, data: bytes, printer_name: str | None = None) -> bool:
        """Send raw TSPL commands via lpr."""
        tmp = tempfile.NamedTemporaryFile(suffix=".tspl", delete=False, mode="wb")
        tmp.write(data)
        tmp.close()
        logger.debug(f"[send_raw] temp file written: {tmp.name}")
        try:
            cmd = ["lpr", "-o", "raw"]
            if printer_name:
                cmd += ["-P", printer_name]
            cmd.append(tmp.name)
            logger.debug(f"[send_raw] running: {cmd}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Exception(f"lpr error: {result.stderr}")
            logger.info(f"TSPL sent to {printer_name or 'default'} ({len(data)} bytes)")
        finally:
            try:
                os.unlink(tmp.name)
            except Exception as e:
                logger.warning(f"[send_raw] could not delete temp file: {e}")
        return True

    def print_pdf(
        self,
        pdf_bytes: bytes,
        printer_name: str | None = None,
        copies: int = 1,
        media_width: float | None = None,
        media_height: float | None = None,
    ) -> bool:
        """Print PDF via lp command."""
        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_file.write(pdf_bytes)
        tmp_file.close()
        tmp_path = tmp_file.name

        try:
            cmd = ["lp", "-n", str(copies)]
            if printer_name:
                cmd += ["-d", printer_name]

            if media_width and media_height:
                w = max(float(media_width), float(media_height))
                h = min(float(media_width), float(media_height))
                cmd += [
                    "-o", f"media=Custom.{w}x{h}mm",
                    "-o", "fit-to-page",
                    "-o", "landscape",
                ]

            cmd.append(tmp_path)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise Exception(f"lp error: {result.stderr}")
            logger.info(f"Printed {copies} copies to {printer_name or 'default'}: {result.stdout.strip()}")

            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Print failed: {e}")
            raise

        return True

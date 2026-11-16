"""PDF/SVG printing endpoint."""

import base64
import logging
import sys
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("pdf", __name__)
logger = logging.getLogger("printbridge")

_font_database = None


def _fonts_dir() -> Path:
    """Return the bundled fonts directory (project root or PyInstaller bundle)."""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "fonts"
    return Path(__file__).resolve().parents[3] / "fonts"


def _get_font_database():
    """Return a cached FontDatabase pre-loaded with bundled fonts."""
    global _font_database
    if _font_database is None:
        from svg2pdf_py import FontDatabase

        fonts_dir = _fonts_dir()
        db = FontDatabase()
        if fonts_dir.is_dir():
            db.load_fonts_dir(str(fonts_dir))
        else:
            logger.warning(
                f"Bundled fonts directory not found: {fonts_dir}; falling back to system fonts"
            )
            db = FontDatabase.system()
        _font_database = db
    return _font_database


def _looks_like_svg(data: bytes) -> bool:
    """Return True if decoded bytes look like an SVG document."""
    head = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    return head.startswith((b"<svg", b"<SVG", b"<?xml", b"<!DOCTYPE svg", b"<!--"))


def _svg_to_pdf(data: bytes) -> bytes:
    """Convert SVG bytes to PDF bytes using svg2pdf-py and bundled fonts."""
    from svg2pdf_py import svg_to_pdf

    svg_text = data.decode("utf-8-sig")
    return svg_to_pdf(svg_text, _get_font_database())


@bp.route("/api/print", methods=["POST"])
def print_pdf():
    """Print a base64-encoded PDF or SVG silently.

    SVG data is converted to PDF with svg2pdf-py, using the bundled
    font database (fonts/ directory) so Chinese (and other Unicode)
    text is rendered correctly.
    """
    try:
        data = request.get_json()
        if not data or "pdf" not in data:
            return jsonify({"error": 'Missing "pdf" field (base64-encoded PDF or SVG)'}), 400

        pdf_base64 = data["pdf"]
        printer_name = data.get("printer", None)
        copies = int(data.get("copies", 1))
        media_width = data.get("mediaWidth", None)
        media_height = data.get("mediaHeight", None)

        if copies < 1 or copies > 99:
            return jsonify({"error": "Copies must be between 1 and 99"}), 400

        try:
            pdf_bytes = base64.b64decode(pdf_base64)
        except Exception:
            return jsonify({"error": "Invalid base64 data"}), 400

        if pdf_bytes[:5] != b"%PDF-":
            if _looks_like_svg(pdf_bytes):
                try:
                    pdf_bytes = _svg_to_pdf(pdf_bytes)
                except ImportError as e:
                    logger.error(f"svg2pdf-py not available: {e}")
                    return jsonify({
                        "error": "svg2pdf-py is required to print SVG data. Install it with: pip install svg2pdf-py"
                    }), 500
                except Exception as e:
                    logger.error(f"SVG to PDF conversion failed: {e}")
                    return jsonify({"error": f"Invalid SVG data: {e}"}), 400
            else:
                return jsonify({"error": "Data is not a valid PDF or SVG"}), 400

        backend = current_app.config["PRINTBRIDGE_BACKEND"]
        backend.print_pdf(pdf_bytes, printer_name, copies, media_width, media_height)

        return jsonify({
            "success": True,
            "printer": printer_name or backend.get_default_printer(),
            "copies": copies,
        })

    except Exception as e:
        logger.error(f"Print route error: {e}")
        return jsonify({"error": str(e)}), 500

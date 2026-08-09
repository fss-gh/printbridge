"""TSPL text command generation — auto-selects TEXT or BITMAP."""

import logging

from .bitmap import render_text_to_bitmap
from .fonts import TSPL_FONT_SIZES
from .text import is_ascii, safe_ascii

logger = logging.getLogger("printbridge")


def tspl_text(
    x: int,
    y: int,
    font_spec: str,
    text: str,
    max_width: int | None = None,
) -> str | bytes | None:
    """Generate TSPL command for text — auto-selects TEXT (str) or BITMAP (bytes).

    Returns str for ASCII, bytes for non-ASCII, or None if empty.
    """
    if not text:
        return None

    if is_ascii(text):
        safe = text.replace('"', "'")
        return f'TEXT {x},{y},{font_spec},"{safe}"'
    else:
        parts = font_spec.replace('"', "").split(",")
        font_id = parts[0].strip()
        y_scale = int(parts[3]) if len(parts) > 3 else 1
        _, base_h = TSPL_FONT_SIZES.get(font_id, (24, 32))
        pixel_size = base_h * y_scale

        bitmap_bytes = render_text_to_bitmap(x, y, text, font_size=pixel_size, max_width=max_width)
        if bitmap_bytes:
            return bitmap_bytes
        else:
            safe = safe_ascii(text, 30)
            if safe:
                return f'TEXT {x},{y},{font_spec},"{safe}"'
            return None

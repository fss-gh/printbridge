"""Unicode/Arabic text bitmap rendering for TSPL labels."""

import logging
import os
import platform

logger = logging.getLogger("printbridge")


def render_text_to_bitmap(
    x: int,
    y: int,
    text: str,
    font_size: int = 24,
    max_width: int | None = None,
) -> bytes | None:
    """Render text as TSPL BITMAP command bytes using Pillow.

    Returns bytes (BITMAP header + raw binary data) or None on failure.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed — Unicode text will be stripped to ASCII")
        return None

    try:
        display_text = text
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display

            reshaped = arabic_reshaper.reshape(text)
            display_text = get_display(reshaped)
        except ImportError:
            pass

        font = None
        if platform.system() == "Windows":
            windir = os.environ.get("WINDIR", "C:\\Windows")
            for name in ["arial.ttf", "tahoma.ttf", "segoeui.ttf"]:
                fp = os.path.join(windir, "Fonts", name)
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, font_size)
                    break
        else:
            for fp in [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, font_size)
                    break

        if not font:
            font = ImageFont.load_default()

        dummy = Image.new("1", (1, 1), 1)
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), display_text, font=font)
        tw = bbox[2] - bbox[0] + 6
        th = bbox[3] - bbox[1] + 6

        if max_width and tw > max_width:
            tw = max_width

        tw = ((tw + 7) // 8) * 8

        img = Image.new("1", (tw, th), 1)
        draw = ImageDraw.Draw(img)
        draw.text((3, -bbox[1] + 3), display_text, font=font, fill=0)

        width_bytes = tw // 8

        raw = bytearray()
        for row_y in range(th):
            for bx in range(width_bytes):
                byte_val = 0
                for bit in range(8):
                    px = bx * 8 + bit
                    if px < tw:
                        pixel = img.getpixel((px, row_y))
                        if pixel == 0:
                            byte_val |= 1 << (7 - bit)
                raw.append(byte_val)

        header = f"BITMAP {x},{y},{width_bytes},{th},0,".encode("ascii")
        return header + bytes(raw)

    except Exception as e:
        logger.error(f"Bitmap text render error: {e}")
        return None

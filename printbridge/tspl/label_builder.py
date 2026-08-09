"""Product label builder for TSPL thermal printers."""

import logging
from datetime import datetime

from .fonts import TSPL_FONT_SIZES
from .text import safe_text
from .text_cmd import tspl_text

logger = logging.getLogger("printbridge")


def build_tspl_label(
    product_name: str = "Product",
    formule_name: str = "",
    width: int = 0,
    height: int = 0,
    position: str = "",
    quantity: int = 1,
    order_ref: str = "",
    client_name: str = "",
    qr_url: str = "",
    shop_name: str = "",
    work_order_id: int = 0,
    label_width_mm: int = 100,
    label_height_mm: int = 50,
    display_options: dict | None = None,
    footer_text: str = "PrintBridge",
) -> bytes:
    """Build TSPL commands for a single product label.

    display_options dict controls what's shown:
        show_barcode (default False),
        show_formule (default True), show_client (default True),
        show_order (default True), show_qr (default True),
        show_position (default True), show_shop_header (default True)
    """
    opts = display_options or {}
    show_barcode = opts.get("show_barcode", False)
    show_formule = opts.get("show_formule", True)
    show_client = opts.get("show_client", True)
    show_order = opts.get("show_order", True)
    show_qr = opts.get("show_qr", True)
    show_position = opts.get("show_position", True)
    show_shop_header = opts.get("show_shop_header", True)
    font_scale = max(1, min(3, int(opts.get("font_scale", 2))))

    dpmm = 8
    w = label_width_mm * dpmm
    h = label_height_mm * dpmm

    s_product = safe_text(product_name, 28)
    s_formule = safe_text(formule_name, 24) if show_formule else ""
    s_position = safe_text(position, 60) if show_position else ""
    s_order = safe_text(order_ref, 20) if show_order else ""
    s_client = safe_text(client_name, 20) if show_client else ""
    s_shop = safe_text(shop_name, 20)
    s_qr = (str(qr_url)[:120] if qr_url else "") if show_qr else ""

    s_date = datetime.now().strftime("%d/%m/%Y")

    is_landscape = label_width_mm > label_height_mm
    is_short = label_height_mm <= 60 and not is_landscape
    direction = 0 if is_landscape else 1

    cmds: list[str | bytes] = [
        f"SIZE {label_width_mm} mm, {label_height_mm} mm",
        "GAP 2 mm, 0 mm",
        f"DIRECTION {direction}",
        "CLS",
    ]

    def _add(x: int, y: int, font_spec: str, text: str, mw: int | None = None) -> None:
        cmd = tspl_text(x, y, font_spec, text, max_width=mw)
        if cmd:
            cmds.append(cmd)

    def _add_wrapped(
        x: int, y: int, font_spec: str, text: str, max_width: int, line_height: int | None = None
    ) -> int:
        if not text:
            return y
        parts = font_spec.replace('"', "").split(",")
        font_id = parts[0].strip()
        x_scale = int(parts[2]) if len(parts) > 2 else 1
        base_w, base_h = TSPL_FONT_SIZES.get(font_id, (24, 32))
        y_scale = int(parts[3]) if len(parts) > 3 else 1
        char_w = base_w * x_scale
        lh = line_height or (base_h * y_scale + 4)
        max_chars = max(4, max_width // char_w)
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip() if current else word
            if len(test) <= max_chars:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if not lines:
            lines = [text]
        for line in lines:
            _add(x, y, font_spec, line, mw=max_width)
            y += lh
        return y

    if is_landscape:
        margin = 20
        text_zone_w = int(w * 0.58)
        qr_zone_x = text_zone_w + 20

        if font_scale == 1:
            f_header = f_title = '"4",0,1,1'
            f_body = '"3",0,1,1'
            f_dim = '"4",0,1,1'
            qr_cell = 5
        elif font_scale == 3:
            f_header = f_title = '"4",0,2,2'
            f_body = '"4",0,1,1'
            f_dim = '"4",0,2,2'
            qr_cell = 7
        else:
            f_header = f_title = '"4",0,1,1'
            f_body = '"3",0,1,1'
            f_dim = '"4",0,2,2'
            qr_cell = 6

        cmds.append(f"BAR {text_zone_w + 8},{10},{2},{h - 20}")

        if s_qr:
            qr_dots = qr_cell * 33
            right_margin = 20
            qr_x = qr_zone_x + (w - qr_zone_x - qr_dots - right_margin) // 2
            qr_y = (h - qr_dots) // 2
            _add(qr_zone_x + 10, qr_y - 22, '"2",0,1,1', s_date)
            cmds.append(f'QRCODE {qr_x},{qr_y},M,{qr_cell},A,0,"{s_qr}"')

        y = 10

        if show_shop_header and s_shop:
            _add(margin, y, f_header, s_shop)
            y += 34
            cmds.append(f"BAR {margin},{y},{text_zone_w - margin * 2},{2}")
            y += 14

        _add(margin, y, f_title, s_product, mw=text_zone_w - margin * 2)
        y += 42

        if s_formule:
            _add(margin, y, f_body, s_formule, mw=text_zone_w - margin * 2)
            y += 32

        _add(margin, y, f_title, f"L: {width} mm")
        y += 36
        _add(margin, y, f_title, f"H: {height} mm")
        y += 40

        cmds.append(f"BAR {margin},{y},{text_zone_w - margin * 2},{2}")
        y += 18

        if s_order:
            _add(margin, y, f_body, f"Order: {s_order}")
            y += 30
        if s_client:
            _add(margin, y, f_body, s_client, mw=text_zone_w - margin * 2)
            y += 30

        if s_position:
            y += 16
            y = _add_wrapped(margin, y, f_title, s_position, max_width=text_zone_w - margin * 2)

        cmds.append(f"BAR {margin},{h - 28},{text_zone_w - margin * 2},{2}")
        _add(margin, h - 22, '"2",0,1,1', f"#{work_order_id} - {footer_text}")

    elif is_short:
        qr_size = min(4, max(2, (h - 20) // 40))
        qr_w_dots = qr_size * 33 + 20
        qr_x = w - qr_w_dots

        if label_height_mm <= 30:
            font_big, font_small, line_h = "3", "2", 20
        elif label_height_mm <= 45:
            font_big, font_small, line_h = "3", "2", 22
        else:
            font_big, font_small, line_h = "4", "3", 28

        fb = f'"{font_big}",0,1,1'
        fs = f'"{font_small}",0,1,1'

        y = 5
        _add(8, y, fb, s_product)
        y += line_h
        _add(8, y, fb, f"{width}x{height} mm")
        y += line_h

        if s_position:
            y = _add_wrapped(8, y, fs, s_position, max_width=qr_x - 16, line_height=line_h - 4)
        elif s_formule:
            _add(8, y, fs, s_formule)
            y += line_h - 4

        info_parts = []
        if s_order:
            info_parts.append(s_order)
        if info_parts and y + line_h < h - 5:
            _add(8, y, fs, " ".join(info_parts))
            y += line_h - 4

        if s_client and y + line_h < h - 5:
            _add(8, y, fs, s_client)

        if s_qr:
            qr_y = max(5, (h - qr_size * 33) // 2)
            _add(qr_x + 4, max(1, qr_y - 16), '"1",0,1,1', s_date)
            cmds.append(f'QRCODE {qr_x},{qr_y},M,{qr_size},A,0,"{s_qr}"')

    else:
        if font_scale == 1:
            f_title = '"4",0,1,1'
            f_body = '"3",0,1,1'
            f_header = '"4",0,1,1'
            f_dim = '"4",0,1,1'
            spacing = max(22, min(30, h // 28))
            qr_cell = 4
        elif font_scale == 3:
            f_title = '"4",0,2,2'
            f_body = '"4",0,2,2'
            f_header = '"4",0,2,2'
            f_dim = '"4",0,2,2'
            spacing = max(45, min(60, h // 14))
            qr_cell = 7
        else:
            f_title = '"4",0,2,2'
            f_body = '"4",0,1,1'
            f_header = '"4",0,1,1'
            f_dim = '"4",0,2,2'
            spacing = max(30, min(45, h // 20))
            qr_cell = 6

        qr_dots = qr_cell * 33 + 20
        bottom_zone = 100 if s_position else 10

        y = 10

        if show_shop_header:
            _add(20, y, f_header, s_shop)
            _add(w - 250, y, f_header, f"#{work_order_id}")
            y += spacing
            cmds.append(f"BAR 10,{y},{w - 20},3")
            y += 15

        _add(20, y, f_dim, f"L {width} x H {height} mm")
        y += spacing + 15

        if s_qr:
            y += 15
            date_x = w // 2 - 40
            _add(date_x, y - 2, '"2",0,1,1', s_date)
            y += 20
            qr_x = w // 2 - (qr_dots // 2)
            cmds.append(f'QRCODE {qr_x},{y},M,{qr_cell},A,0,"{s_qr}"')
            y += qr_dots + 10

        if s_product and y + spacing < h - bottom_zone:
            _add(20, y, f_body, s_product)
            y += spacing

        if s_formule and y + spacing < h - bottom_zone:
            _add(20, y, f_body, s_formule)
            y += spacing

        if s_order and y + spacing < h - bottom_zone:
            _add(20, y, f_body, f"Order: {s_order}")
            y += spacing

        if s_client and y + spacing < h - bottom_zone:
            _add(20, y, f_body, s_client)
            y += spacing

        if s_position:
            cmds.append(f"BAR 10,{h - 95},{w - 20},3")
            _add_wrapped(20, h - 80, f_body, s_position, max_width=w - 40)

    cmds.append("PRINT 1,1")

    output = bytearray()
    for item in cmds:
        if isinstance(item, bytes):
            output.extend(item)
        else:
            output.extend(item.encode("ascii", errors="replace"))
        output.extend(b"\r\n")
    return bytes(output)

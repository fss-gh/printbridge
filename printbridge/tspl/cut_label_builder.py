"""Cut label builder for TSPL thermal printers."""

import logging
from datetime import date

from .text import safe_text
from .text_cmd import tspl_text

logger = logging.getLogger("printbridge")


def build_tspl_cut_label(
    position: str = "",
    bar_info: str = "",
    profile_name: str = "",
    profile_ref: str = "",
    cut_name: str = "",
    finishing: str = "",
    length: int = 0,
    angles: str = "",
    quantity: int = 1,
    bin_number: int = 0,
    shop_name: str = "",
    label_width_mm: int = 45,
    label_height_mm: int = 35,
    order_ref: str = "",
    source: str = "",
    footer_text: str = "PrintBridge",
) -> bytes:
    """Build TSPL commands for a single cut label (thermal printer).

    Default label: 45x35mm landscape (360x280 dots @ 203 DPI).
    """
    logger.debug(
        f"[build_tspl_cut_label] profile_name={profile_name!r} profile_ref={profile_ref!r} "
        f"cut_name={cut_name!r} length={length} angles={angles!r} "
        f"position={position!r} bar_info={bar_info!r} finishing={finishing!r} "
        f"bin_number={bin_number} order_ref={order_ref!r} label={label_width_mm}x{label_height_mm}mm"
    )

    dpmm = 8
    w = label_width_mm * dpmm
    h = label_height_mm * dpmm

    s_ref = safe_text(profile_ref, 22) if profile_ref else ""
    s_finishing = safe_text(finishing, 16) if finishing else ""
    s_angles = safe_text(angles, 12) if angles and angles not in ("—", "-") else ""
    s_bin = str(bin_number) if bin_number else ""
    s_length = str(length) if length else ""
    s_cut_name = safe_text(cut_name, 4) if cut_name else ""

    if source == "waste":
        s_position = date.today().strftime("%d/%m/%Y")
    else:
        s_position = safe_text(str(position), 16) if position else ""

    raw_bar = str(bar_info) if bar_info else ""
    if " — " in raw_bar:
        raw_bar = raw_bar.split(" — ", 1)[1]
    s_bar_info = safe_text(raw_bar, 10) if raw_bar else ""
    s_order = safe_text(f"#{order_ref}", 10) if order_ref else ""

    cmds: list[str | bytes] = [
        f"SIZE {label_width_mm} mm, {label_height_mm} mm",
        "GAP 2 mm, 0 mm",
        "DIRECTION 0",
        "CLS",
    ]

    def _add(x: int, y: int, font_spec: str, text: str, mw: int | None = None) -> None:
        cmd = tspl_text(x, y, font_spec, text, max_width=mw)
        if cmd:
            cmds.append(cmd)

    margin = 6
    border_thick = 3

    cmds.append(f"BOX {margin},{margin},{w - margin},{h - margin},{border_thick}")

    inner_l = margin + border_thick + 14
    inner_r = w - margin - border_thick - 3
    inner_w = inner_r - inner_l

    tiny_h = 12
    small_h = 20
    med_h = 24
    big_h = 48

    top_inner = margin + border_thick + 4
    ref_zone_h = med_h + 6
    ref_y = top_inner + 2
    ref_bot = top_inner + ref_zone_h

    border_bot = h - margin - border_thick
    pad = 6
    footer_y = border_bot - pad - small_h
    detail_y = footer_y - 6 - small_h
    finishing_y = detail_y - 6 - small_h
    pos_y = finishing_y - 6 - med_h

    len_zone_top = ref_bot + 10

    digits = len(s_length)
    if digits <= 3:
        lsx, lsy = 2, 2
    elif digits == 4:
        lsx, lsy = 1, 2
    else:
        lsx, lsy = 1, 1
    len_char_w = 32 * lsx
    len_text_w = digits * len_char_w

    bin_zone_w = 32 + 14
    divider_x = inner_r - bin_zone_w
    cmds.append(f"BAR {divider_x},{top_inner},{2},{ref_zone_h}")

    if s_ref:
        _add(inner_l, ref_y, '"3",0,1,1', s_ref, mw=divider_x - inner_l - 4)

    if s_bin:
        bin_cx = divider_x + 7
        bin_cy = top_inner + max(0, (ref_zone_h - big_h) // 2)
        cmds.append(f'TEXT {bin_cx},{bin_cy},"5",0,1,1,"{s_bin}"')

    cmds.append(f"BAR {inner_l},{ref_bot + 1},{inner_r - inner_l},{2}")

    if s_length:
        gap = 32
        tag_w = (gap + len(s_cut_name) * len_char_w) if s_cut_name else 0
        total_text_w = len_text_w + tag_w
        cx = max(inner_l, inner_l + (inner_w - total_text_w) // 2)
        cy = len_zone_top
        cmds.append(f'TEXT {cx},{cy},"5",0,{lsx},{lsy},"{s_length}"')
        if s_cut_name:
            tag_x = cx + len_text_w + gap
            cmds.append(f'TEXT {tag_x},{cy},"5",0,{lsx},{lsy},"{s_cut_name}"')

    if s_position:
        pos_text_w = len(s_position) * 16
        pos_cx = max(inner_l, inner_l + (inner_w - pos_text_w) // 2)
        _add(pos_cx, pos_y, '"3",0,1,1', s_position)

    if s_finishing:
        fin_text_w = len(s_finishing) * 12
        fin_cx = max(inner_l, inner_l + (inner_w - fin_text_w) // 2)
        _add(fin_cx, finishing_y, '"2",0,1,1', s_finishing)

    detail_parts = [p for p in [s_bar_info, s_angles] if p]
    s_detail = "  ".join(detail_parts)
    if s_detail:
        _add(inner_l, detail_y, '"2",0,1,1', s_detail, mw=inner_w)

    s_footer = f"By {footer_text}"
    footer_offset = (small_h - tiny_h) // 2
    if s_order:
        _add(inner_l, footer_y, '"2",0,1,1', s_order)
        footer_text_w = len(s_footer) * 8
        footer_rx = inner_r - footer_text_w
        _add(max(inner_l, footer_rx), footer_y + footer_offset, '"1",0,1,1', s_footer)
    else:
        footer_text_w = len(s_footer) * 8
        footer_cx = max(inner_l, inner_l + (inner_w - footer_text_w) // 2)
        _add(footer_cx, footer_y + footer_offset, '"1",0,1,1', s_footer)

    cmds.append("PRINT 1")

    output = bytearray()
    for item in cmds:
        if isinstance(item, bytes):
            output.extend(item)
        else:
            output.extend(item.encode("ascii", errors="replace"))
        output.extend(b"\r\n")
    return bytes(output)

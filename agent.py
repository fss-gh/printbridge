"""
PrintBridge — Silent Local Printing Service

A lightweight local print agent that runs in the system tray.
Any web application can send print jobs via HTTP to localhost,
and this agent prints them silently to the selected printer.

Supports:
  - Silent PDF printing (any system printer)
  - TSPL label printing (thermal printers: TSC, Xprinter, etc.)
  - QR codes, barcode support
  - Unicode/Arabic text rendering via bitmap
  - Custom label templates

Works on macOS, Windows, and Linux.

Configuration: see config.json (or environment variables).
"""

import sys
import os
import json
import base64
import tempfile
import subprocess
import platform
import threading
import logging
from pathlib import Path

# Windows-only: pywin32 for native printer access
if platform.system() == 'Windows':
    import win32print
    import win32api

from flask import Flask, request, jsonify
from flask_cors import CORS

# ─── Logging ─────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / 'config.json'

DEFAULT_CONFIG = {
    'port': 9120,
    'cors_origins': ['http://localhost:*', 'http://127.0.0.1:*'],
    'log_dir': '~/.printbridge',
    'label_defaults': {
        'width_mm': 100,
        'height_mm': 150,
        'dpmm': 8,
        'gap_mm': 2,
    },
    'footer_text': 'PrintBridge',
    'tray_name': 'PrintBridge',
}

def load_config():
    """Load configuration from config.json, falling back to defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                user_cfg = json.load(f)
            cfg.update(user_cfg)
        except Exception as e:
            print(f'Warning: could not parse config.json: {e}')
    # Allow env var overrides
    if os.environ.get('PRINTBRIDGE_PORT'):
        cfg['port'] = int(os.environ['PRINTBRIDGE_PORT'])
    if os.environ.get('PRINTBRIDGE_FOOTER'):
        cfg['footer_text'] = os.environ['PRINTBRIDGE_FOOTER']
    if os.environ.get('PRINTBRIDGE_TRAY_NAME'):
        cfg['tray_name'] = os.environ['PRINTBRIDGE_TRAY_NAME']
    return cfg

CONFIG = load_config()

LOG_DIR = Path(os.path.expanduser(CONFIG.get('log_dir', '~/.printbridge')))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('printbridge')

# ─── Flask App ────────────────────────────────────────────────────────
app = Flask(__name__)

# Allow CORS from configured origins
CORS(app, origins=CONFIG.get('cors_origins', ['http://localhost:*', 'http://127.0.0.1:*']))

SYSTEM = platform.system()  # 'Darwin', 'Windows', 'Linux'
PORT = CONFIG.get('port', 9120)
VERSION = '1.0.0'
FOOTER_TEXT = CONFIG.get('footer_text', 'PrintBridge')
TRAY_NAME = CONFIG.get('tray_name', 'PrintBridge')


def get_printers():
    """List available printers from the OS."""
    try:
        if SYSTEM == 'Darwin' or SYSTEM == 'Linux':
            # Use lpstat -a (not -p) because -p output is locale-dependent
            # -a output always starts with printer name: "PrinterName accepting ..."
            result = subprocess.run(
                ['lpstat', '-a'],
                capture_output=True, text=True, timeout=5
            )
            printers = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line:
                    # First word is the printer name
                    name = line.split()[0]
                    printers.append(name)
            return printers

        elif SYSTEM == 'Windows':
            # Use win32print for reliable printer enumeration
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printer_list = win32print.EnumPrinters(flags, None, 2)
            return [p['pPrinterName'] for p in printer_list]

        return []
    except Exception as e:
        logger.error(f'Error listing printers: {e}')
        return []


def get_default_printer():
    """Get the system default printer."""
    try:
        if SYSTEM == 'Darwin' or SYSTEM == 'Linux':
            result = subprocess.run(
                ['lpstat', '-d'],
                capture_output=True, text=True, timeout=5
            )
            # Output: "system default destination: PrinterName"
            parts = result.stdout.strip().split(':')
            if len(parts) >= 2:
                return parts[1].strip()
        elif SYSTEM == 'Windows':
            return win32print.GetDefaultPrinter()
    except Exception as e:
        logger.error(f'Error getting default printer: {e}')
    return None


def _delayed_cleanup(path, delay=15):
    """Delete a temp file after a delay (Windows needs time for async print)."""
    import time
    time.sleep(delay)
    try:
        os.unlink(path)
    except Exception:
        pass


def _find_sumatra():
    """Find SumatraPDF executable on Windows."""
    candidates = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'SumatraPDF', 'SumatraPDF.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'SumatraPDF', 'SumatraPDF.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'SumatraPDF', 'SumatraPDF.exe'),
        # Portable version next to agent
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SumatraPDF.exe'),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    # Check PATH
    try:
        result = subprocess.run(
            ['where', 'SumatraPDF.exe'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split('\n')[0].strip()
    except Exception:
        pass
    return None


def print_pdf(pdf_bytes, printer_name=None, copies=1, media_width=None, media_height=None):
    """Print a PDF file silently using OS commands.
    
    Args:
        pdf_bytes: Raw PDF bytes
        printer_name: Target printer name (None = default)
        copies: Number of copies
        media_width: Label width in mm (for thermal printers)
        media_height: Label height in mm (for thermal printers)
    """
    # Save to temp file
    tmp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp_file.write(pdf_bytes)
    tmp_file.close()
    tmp_path = tmp_file.name

    try:
        if SYSTEM == 'Darwin' or SYSTEM == 'Linux':
            cmd = ['lp', '-n', str(copies)]
            if printer_name:
                cmd += ['-d', printer_name]
            
            # Thermal printer: set custom media size, landscape, fit-to-page
            if media_width and media_height:
                # Use the larger dimension as width (landscape)
                w = max(float(media_width), float(media_height))
                h = min(float(media_width), float(media_height))
                cmd += [
                    '-o', f'media=Custom.{w}x{h}mm',
                    '-o', 'fit-to-page',
                    '-o', 'landscape',
                ]
            
            cmd.append(tmp_path)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise Exception(f'lp error: {result.stderr}')
            logger.info(f'Printed {copies} copies to {printer_name or "default"}: {result.stdout.strip()}')
            # Safe to delete immediately on macOS/Linux (lp copies the file)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        elif SYSTEM == 'Windows':
            target_printer = printer_name or win32print.GetDefaultPrinter()
            printed = False

            # Strategy 1: SumatraPDF CLI (most reliable for silent printing)
            sumatra = _find_sumatra()
            if sumatra:
                try:
                    cmd = [
                        sumatra,
                        '-print-to', target_printer,
                        '-print-settings', f'{copies}x',
                        '-silent',
                        tmp_path
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        printed = True
                        logger.info(f'Printed {copies} copies to {target_printer} via SumatraPDF')
                    else:
                        logger.warning(f'SumatraPDF failed (code {result.returncode}): {result.stderr}')
                except Exception as e:
                    logger.warning(f'SumatraPDF error: {e}')

            # Strategy 2: PowerShell Start-Process with PrintTo verb
            if not printed:
                try:
                    # PowerShell printing is synchronous and reliable
                    ps_cmd = (
                        f'Start-Process -FilePath "{tmp_path}" '
                        f'-Verb PrintTo -ArgumentList \'"{target_printer}"\' '
                        f'-WindowStyle Hidden -Wait'
                    )
                    for _ in range(copies):
                        result = subprocess.run(
                            ['powershell', '-NoProfile', '-Command', ps_cmd],
                            capture_output=True, text=True, timeout=120
                        )
                        if result.returncode != 0:
                            raise Exception(f'PowerShell exit {result.returncode}: {result.stderr}')
                    printed = True
                    logger.info(f'Printed {copies} copies to {target_printer} via PowerShell')
                except Exception as e:
                    logger.warning(f'PowerShell print failed: {e}')

            # Strategy 3: ShellExecute fallback (original approach)
            if not printed:
                try:
                    for _ in range(copies):
                        win32api.ShellExecute(
                            0, 'printto', tmp_path,
                            f'"{target_printer}"', '.', 0
                        )
                    printed = True
                    logger.info(f'Printed {copies} copies to {target_printer} via ShellExecute')
                except Exception as e:
                    logger.error(f'ShellExecute also failed: {e}')
                    raise Exception(
                        f'All print methods failed for printer "{target_printer}". '
                        f'Please install SumatraPDF for reliable silent printing: '
                        f'https://www.sumatrapdfreader.org/download-free-pdf-viewer'
                    )

            # Windows: delay temp file cleanup (async print needs time to read it)
            cleanup_thread = threading.Thread(
                target=_delayed_cleanup, args=(tmp_path, 30), daemon=True
            )
            cleanup_thread.start()

        return True
    except Exception as e:
        logger.error(f'Print failed: {e}')
        raise


# ─── API Routes ───────────────────────────────────────────────────────

@app.route('/api/status', methods=['GET'])
def status():
    """Health check — web app uses this to detect if the agent is running."""
    return jsonify({
        'status': 'ok',
        'version': VERSION,
        'platform': SYSTEM,
        'port': PORT,
        'tspl': True,
    })


@app.route('/api/printers', methods=['GET'])
def list_printers_route():
    """List available printers."""
    printers = get_printers()
    default = get_default_printer()
    return jsonify({
        'printers': printers,
        'default': default,
    })


@app.route('/api/print', methods=['POST'])
def print_route():
    """Print a base64-encoded PDF silently."""
    try:
        data = request.get_json()
        if not data or 'pdf' not in data:
            return jsonify({'error': 'Missing "pdf" field (base64-encoded PDF)'}), 400

        pdf_base64 = data['pdf']
        printer_name = data.get('printer', None)
        copies = int(data.get('copies', 1))
        media_width = data.get('mediaWidth', None)  # mm, for thermal
        media_height = data.get('mediaHeight', None)  # mm, for thermal

        if copies < 1 or copies > 99:
            return jsonify({'error': 'Copies must be between 1 and 99'}), 400

        # Decode base64
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
        except Exception:
            return jsonify({'error': 'Invalid base64 data'}), 400

        # Validate it's a PDF
        if not pdf_bytes[:5] == b'%PDF-':
            return jsonify({'error': 'Data is not a valid PDF'}), 400

        # Print
        print_pdf(pdf_bytes, printer_name, copies, media_width, media_height)

        return jsonify({
            'success': True,
            'printer': printer_name or get_default_printer(),
            'copies': copies,
        })

    except Exception as e:
        logger.error(f'Print route error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── TSPL Label Printing ──────────────────────────────────────────────

def _is_ascii(text):
    """Check if text is pure ASCII (can use TSPL TEXT command)."""
    if not text:
        return True
    try:
        text.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False


def _safe_ascii(text, max_len=30):
    """Convert text to safe ASCII for TSPL TEXT command."""
    import unicodedata
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(text))
    ascii_text = nfkd.encode('ascii', 'ignore').decode('ascii')
    ascii_text = ascii_text.replace('"', "'")
    return ascii_text[:max_len]


def _safe_text(text, max_len=30):
    """Sanitize text for label (keep Unicode, just remove quotes and trim)."""
    if not text:
        return ''
    t = str(text).replace('"', "'")
    return t[:max_len]


# TSPL font sizes: font_id -> (char_width, char_height) in dots at 1x scale
_TSPL_FONT_SIZES = {
    '1': (8, 12), '2': (12, 20), '3': (16, 24), '4': (24, 32), '5': (32, 48),
}


def _text_to_bitmap_bytes(x, y, text, font_size=24, max_width=None):
    """Render text as TSPL BITMAP command bytes using Pillow.

    Returns bytes (BITMAP header + raw binary data) or None on failure.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning('Pillow not installed — Arabic text will be stripped to ASCII')
        return None

    try:
        # Try Arabic reshaping if available
        display_text = text
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            reshaped = arabic_reshaper.reshape(text)
            display_text = get_display(reshaped)
        except ImportError:
            pass  # Pillow may still handle Arabic via harfbuzz

        # Find a font that supports Arabic
        font = None
        if platform.system() == 'Windows':
            windir = os.environ.get('WINDIR', 'C:\\Windows')
            for name in ['arial.ttf', 'tahoma.ttf', 'segoeui.ttf']:
                fp = os.path.join(windir, 'Fonts', name)
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, font_size)
                    break
        else:
            for fp in ['/System/Library/Fonts/Supplemental/Arial.ttf',
                       '/System/Library/Fonts/Helvetica.ttc',
                       '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, font_size)
                    break

        if not font:
            font = ImageFont.load_default()

        # Measure text
        dummy = Image.new('1', (1, 1), 1)
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), display_text, font=font)
        tw = bbox[2] - bbox[0] + 6
        th = bbox[3] - bbox[1] + 6

        if max_width and tw > max_width:
            tw = max_width

        # Width must be multiple of 8 for TSPL BITMAP
        tw = ((tw + 7) // 8) * 8

        # Render
        img = Image.new('1', (tw, th), 1)  # white
        draw = ImageDraw.Draw(img)
        draw.text((3, -bbox[1] + 3), display_text, font=font, fill=0)  # black

        width_bytes = tw // 8

        # Build raw binary data — each bit: 1=black (print), 0=white
        raw = bytearray()
        for row_y in range(th):
            for bx in range(width_bytes):
                byte_val = 0
                for bit in range(8):
                    px = bx * 8 + bit
                    if px < tw:
                        pixel = img.getpixel((px, row_y))
                        if pixel == 0:  # black
                            byte_val |= (1 << (7 - bit))
                raw.append(byte_val)

        # BITMAP command: header (ASCII) + raw binary data
        header = f'BITMAP {x},{y},{width_bytes},{th},0,'.encode('ascii')
        return header + bytes(raw)

    except Exception as e:
        logger.error(f'Bitmap text render error: {e}')
        return None


def _tspl_text(x, y, font_spec, text, max_width=None):
    """Generate TSPL command for text — auto-selects TEXT (str) or BITMAP (bytes).

    Returns str for ASCII, bytes for non-ASCII, or None if empty.
    """
    if not text:
        return None

    if _is_ascii(text):
        safe = text.replace('"', "'")
        return f'TEXT {x},{y},{font_spec},"{safe}"'
    else:
        # Parse font_spec for pixel size
        parts = font_spec.replace('"', '').split(',')
        font_id = parts[0].strip()
        y_scale = int(parts[3]) if len(parts) > 3 else 1
        base_w, base_h = _TSPL_FONT_SIZES.get(font_id, (24, 32))
        pixel_size = base_h * y_scale

        bitmap_bytes = _text_to_bitmap_bytes(x, y, text, font_size=pixel_size, max_width=max_width)
        if bitmap_bytes:
            return bitmap_bytes
        else:
            safe = _safe_ascii(text, 30)
            if safe:
                return f'TEXT {x},{y},{font_spec},"{safe}"'
            return None


def build_tspl_label(
    product_name='Produit',
    formule_name='',
    width=0,
    height=0,
    position='',
    quantity=1,
    order_ref='',
    client_name='',
    qr_url='',
    shop_name='',
    work_order_id=0,
    label_width_mm=100,
    label_height_mm=50,
    display_options=None,
):
    """Build TSPL commands for a single product label.

    display_options dict controls what's shown:
        show_barcode (default False),
        show_formule (default True), show_client (default True),
        show_order (default True), show_qr (default True),
        show_position (default True), show_shop_header (default True)
    """
    opts = display_options or {}
    show_barcode = opts.get('show_barcode', False)

    show_formule = opts.get('show_formule', True)
    show_client = opts.get('show_client', True)
    show_order = opts.get('show_order', True)
    show_qr = opts.get('show_qr', True)
    show_position = opts.get('show_position', True)
    show_shop_header = opts.get('show_shop_header', True)
    # font_scale: 1=small, 2=medium (default), 3=large
    font_scale = max(1, min(3, int(opts.get('font_scale', 2))))

    dpmm = 8  # 203 DPI
    w = label_width_mm * dpmm
    h = label_height_mm * dpmm

    # Keep Unicode text (for bitmap rendering of Arabic etc)
    s_product = _safe_text(product_name, 28)
    s_formule = _safe_text(formule_name, 24) if show_formule else ''
    s_position = _safe_text(position, 60) if show_position else ''
    s_order = _safe_text(order_ref, 20) if show_order else ''
    s_client = _safe_text(client_name, 20) if show_client else ''
    s_shop = _safe_text(shop_name, 20)
    s_qr = (str(qr_url)[:120] if qr_url else '') if show_qr else ''

    # Current print date
    from datetime import datetime
    s_date = datetime.now().strftime('%d/%m/%Y')

    is_landscape = label_width_mm > label_height_mm
    is_short = label_height_mm <= 60 and not is_landscape

    # Landscape: DIRECTION 0 (origin top-left), Portrait: DIRECTION 1
    direction = 0 if is_landscape else 1

    cmds = [
        f'SIZE {label_width_mm} mm, {label_height_mm} mm',
        'GAP 2 mm, 0 mm',
        f'DIRECTION {direction}',
        'CLS',
    ]

    def _add(x, y, font_spec, text, mw=None):
        """Append a text command (TEXT or BITMAP) to cmds."""
        cmd = _tspl_text(x, y, font_spec, text, max_width=mw)
        if cmd:
            cmds.append(cmd)

    def _add_wrapped(x, y, font_spec, text, max_width, line_height=None):
        """Render text with word-wrapping.  Returns the new y after all lines."""
        if not text:
            return y
        # Estimate char width from font spec
        parts = font_spec.replace('"', '').split(',')
        font_id = parts[0].strip()
        x_scale = int(parts[2]) if len(parts) > 2 else 1
        base_w = _TSPL_FONT_SIZES.get(font_id, (24, 32))[0]
        base_h = _TSPL_FONT_SIZES.get(font_id, (24, 32))[1]
        y_scale = int(parts[3]) if len(parts) > 3 else 1
        char_w = base_w * x_scale
        lh = line_height or (base_h * y_scale + 4)
        max_chars = max(4, max_width // char_w)
        # Word-wrap
        words = text.split()
        lines = []
        current = ''
        for word in words:
            test = f'{current} {word}'.strip() if current else word
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
        # ═══ LANDSCAPE LAYOUT (width > height, e.g. 100×60mm) ═══
        # Left: text info (~58%) | vertical bar | Right: QR code (~42%)
        margin = 20
        text_zone_w = int(w * 0.58)
        qr_zone_x = text_zone_w + 20

        # Font sizing
        if font_scale == 1:
            f_header = '"4",0,1,1'
            f_title = '"4",0,1,1'
            f_body = '"3",0,1,1'
            f_dim = '"4",0,1,1'
            qr_cell = 5
        elif font_scale == 3:
            f_header = '"4",0,2,2'
            f_title = '"4",0,2,2'
            f_body = '"4",0,1,1'
            f_dim = '"4",0,2,2'
            qr_cell = 7
        else:  # default
            f_header = '"4",0,1,1'
            f_title = '"4",0,1,1'
            f_body = '"3",0,1,1'
            f_dim = '"4",0,2,2'
            qr_cell = 6

        # ── Vertical separator ──
        cmds.append(f'BAR {text_zone_w + 8},{10},{2},{h - 20}')

        # ── QR code (centered in right zone with padding) ──
        if s_qr:
            qr_dots = qr_cell * 33
            right_margin = 20
            qr_x = qr_zone_x + (w - qr_zone_x - qr_dots - right_margin) // 2
            qr_y = (h - qr_dots) // 2
            # Print date above QR code
            _add(qr_zone_x + 10, qr_y - 22, '"2",0,1,1', s_date)
            cmds.append(f'QRCODE {qr_x},{qr_y},M,{qr_cell},A,0,"{s_qr}"')

        # ── Left side text layout ──
        y = 10

        # Shop header
        if show_shop_header and s_shop:
            _add(margin, y, f_header, s_shop)
            y += 34
            cmds.append(f'BAR {margin},{y},{text_zone_w - margin * 2},{2}')
            y += 14

        # Product name
        _add(margin, y, f_title, s_product, mw=text_zone_w - margin * 2)
        y += 42

        # Formule
        if s_formule:
            _add(margin, y, f_body, s_formule, mw=text_zone_w - margin * 2)
            y += 32

        # Dimensions (two lines to avoid overflow into QR zone)
        _add(margin, y, f_title, f'L: {width} mm')
        y += 36
        _add(margin, y, f_title, f'H: {height} mm')
        y += 40

        # Separator
        cmds.append(f'BAR {margin},{y},{text_zone_w - margin * 2},{2}')
        y += 18

        # Order ref + Client
        if s_order:
            _add(margin, y, f_body, f'Cmd: {s_order}')
            y += 30
        if s_client:
            _add(margin, y, f_body, s_client, mw=text_zone_w - margin * 2)
            y += 30

        # Position (below client, with extra spacing for readability)
        if s_position:
            y += 16  # extra spacing
            y = _add_wrapped(margin, y, f_title, s_position, max_width=text_zone_w - margin * 2)

        # Footer
        cmds.append(f'BAR {margin},{h - 28},{text_zone_w - margin * 2},{2}')
        _add(margin, h - 22, '"2",0,1,1', f'#{work_order_id} - {FOOTER_TEXT}')

    elif is_short:
        # ═══ COMPACT HORIZONTAL LAYOUT (≤60mm height, portrait) ═══
        qr_size = min(4, max(2, (h - 20) // 40))
        qr_w_dots = qr_size * 33 + 20
        qr_x = w - qr_w_dots

        if label_height_mm <= 30:
            font_big, font_small, line_h = '3', '2', 20
        elif label_height_mm <= 45:
            font_big, font_small, line_h = '3', '2', 22
        else:
            font_big, font_small, line_h = '4', '3', 28

        fb = f'"{font_big}",0,1,1'
        fs = f'"{font_small}",0,1,1'

        y = 5
        _add(8, y, fb, s_product)
        y += line_h
        _add(8, y, fb, f'{width}x{height} mm')
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
            _add(8, y, fs, ' '.join(info_parts))
            y += line_h - 4

        if s_client and y + line_h < h - 5:
            _add(8, y, fs, s_client)

        if s_qr:
            qr_y = max(5, (h - qr_size * 33) // 2)
            # Print date above QR code
            _add(qr_x + 4, max(1, qr_y - 16), '"1",0,1,1', s_date)
            cmds.append(f'QRCODE {qr_x},{qr_y},M,{qr_size},A,0,"{s_qr}"')

    else:
        # ═══ SPLIT CARD LAYOUT (>60mm, portrait) ═══
        # Dimensions + QR top, details middle, position bottom
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
        else:  # font_scale == 2 (default)
            f_title = '"4",0,2,2'
            f_body = '"4",0,1,1'
            f_header = '"4",0,1,1'
            f_dim = '"4",0,2,2'
            spacing = max(30, min(45, h // 20))
            qr_cell = 6

        qr_dots = qr_cell * 33 + 20
        # Bottom zone reserved for position
        bottom_zone = 100 if s_position else 10

        y = 10

        # ── Header ──
        if show_shop_header:
            _add(20, y, f_header, s_shop)
            _add(w - 250, y, f_header, f'OF #{work_order_id}')
            y += spacing
            cmds.append(f'BAR 10,{y},{w - 20},3')
            y += 15

        # ── Dimensions (large) ──
        _add(20, y, f_dim, f'L {width} x H {height} mm')
        y += spacing + 15

        # ── QR code (centered) ──
        if s_qr:
            y += 15  # extra gap before QR
            # Print date above QR code
            date_x = w // 2 - 40
            _add(date_x, y - 2, '"2",0,1,1', s_date)
            y += 20
            qr_x = w // 2 - (qr_dots // 2)
            cmds.append(f'QRCODE {qr_x},{y},M,{qr_cell},A,0,"{s_qr}"')
            y += qr_dots + 10

        # ── Details (with overflow protection) ──
        if s_product and y + spacing < h - bottom_zone:
            _add(20, y, f_body, s_product)
            y += spacing

        if s_formule and y + spacing < h - bottom_zone:
            _add(20, y, f_body, s_formule)
            y += spacing

        if s_order and y + spacing < h - bottom_zone:
            _add(20, y, f_body, f'Cmd: {s_order}')
            y += spacing

        if s_client and y + spacing < h - bottom_zone:
            _add(20, y, f_body, s_client)
            y += spacing

        # ── Bottom: Position ──
        if s_position:
            cmds.append(f'BAR 10,{h - 95},{w - 20},3')
            _add_wrapped(20, h - 80, f_body, s_position, max_width=w - 40)

    cmds.append('PRINT 1,1')

    # Build output as bytes — cmds can be str (TEXT) or bytes (BITMAP)
    output = bytearray()
    for item in cmds:
        if isinstance(item, bytes):
            output.extend(item)
        else:
            output.extend(item.encode('ascii', errors='replace'))
        output.extend(b'\r\n')
    return bytes(output)


def send_tspl_raw(tspl_commands, printer_name=None):
    """Send raw TSPL commands to a printer. Accepts str or bytes."""
    if isinstance(tspl_commands, str):
        raw = tspl_commands.encode('ascii', errors='replace')
    else:
        raw = tspl_commands
    target_printer = printer_name

    logger.debug(f'[send_tspl_raw] platform={SYSTEM} printer={target_printer!r} raw_bytes={len(raw)}')
    logger.debug(f'[send_tspl_raw] first 300 bytes: {raw[:300]}')

    if SYSTEM in ('Darwin', 'Linux'):
        tmp = tempfile.NamedTemporaryFile(suffix='.tspl', delete=False, mode='wb')
        tmp.write(raw)
        tmp.close()
        logger.debug(f'[send_tspl_raw] temp file written: {tmp.name}')
        try:
            cmd = ['lpr', '-o', 'raw']
            if target_printer:
                cmd += ['-P', target_printer]
            cmd.append(tmp.name)
            logger.debug(f'[send_tspl_raw] running: {cmd}')
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            logger.debug(f'[send_tspl_raw] lpr returncode={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}')
            if result.returncode != 0:
                raise Exception(f'lpr error: {result.stderr}')
            logger.info(f'TSPL sent to {target_printer or "default"} ({len(raw)} bytes)')
        finally:
            try:
                os.unlink(tmp.name)
                logger.debug(f'[send_tspl_raw] temp file deleted: {tmp.name}')
            except Exception as e:
                logger.warning(f'[send_tspl_raw] could not delete temp file: {e}')

    elif SYSTEM == 'Windows':
        if not target_printer:
            target_printer = win32print.GetDefaultPrinter()
            logger.debug(f'[send_tspl_raw] resolved default printer: {target_printer!r}')

        # Send directly via win32print (no subprocess needed).
        # Previously used subprocess.run([sys.executable, 'tspl_sender.py', ...])
        # but sys.executable in a frozen PyInstaller .exe points to the .exe itself,
        # causing it to re-launch the agent instead of running the script.
        logger.debug(f'[send_tspl_raw] opening win32print handle for {target_printer!r}')
        h = win32print.OpenPrinter(target_printer)
        try:
            win32print.StartDocPrinter(h, 1, ('TSPL Label', None, 'RAW'))
            win32print.StartPagePrinter(h)
            written = win32print.WritePrinter(h, raw)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
            logger.info(f'TSPL sent to {target_printer} ({written} bytes written)')
            logger.debug(f'[send_tspl_raw] win32print write completed: {written}/{len(raw)} bytes')
        except Exception as e:
            logger.error(f'win32print error: {e}')
            raise
        finally:
            win32print.ClosePrinter(h)
            logger.debug(f'[send_tspl_raw] win32print handle closed')

    return True


@app.route('/api/test-tspl', methods=['POST'])
def test_tspl_route():
    """Send a simple test TSPL label to verify printer connectivity."""
    try:
        data = request.get_json() or {}
        printer_name = data.get('printer', None)
        label_width = int(data.get('labelWidth', 100))
        label_height = int(data.get('labelHeight', 150))

        test_tspl = (
            f"SIZE {label_width} mm, {label_height} mm\r\n"
            "GAP 2 mm, 0 mm\r\n"
            "DIRECTION 1\r\n"
            "CLS\r\n"
            f'TEXT 50,30,"4",0,1,1,"PrintBridge Test"\r\n'
            f'TEXT 50,80,"3",0,1,1,"{label_width}x{label_height}mm"\r\n'
            "BAR 30,120,740,2\r\n"
            f'TEXT 50,140,"4",0,1,1,"Printer: {printer_name or "default"}"\r\n'
            f'TEXT 50,190,"3",0,1,1,"{FOOTER_TEXT}"\r\n'
            "PRINT 1,1\r\n"
        )

        logger.info(f'TEST TSPL: sending test label ({len(test_tspl)} bytes)')
        send_tspl_raw(test_tspl, printer_name)

        return jsonify({'success': True, 'method': 'test', 'bytes': len(test_tspl)})
    except Exception as e:
        logger.error(f'Test TSPL error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/print-tspl', methods=['POST'])
def print_tspl_route():
    """Send raw TSPL commands directly to a printer.

    Request body:
        tspl: str or list[str] — raw TSPL commands
        printer: str (optional) — target printer name
    """
    try:
        data = request.get_json()
        if not data or 'tspl' not in data:
            return jsonify({'error': 'Missing "tspl" field (raw TSPL commands)'}), 400

        printer_name = data.get('printer', None)
        tspl_data = data['tspl']

        if isinstance(tspl_data, list):
            tspl_str = '\r\n'.join(tspl_data)
        else:
            tspl_str = str(tspl_data)

        if not tspl_str.endswith('\r\n'):
            tspl_str += '\r\n'

        send_tspl_raw(tspl_str, printer_name)

        return jsonify({
            'success': True,
            'printer': printer_name or get_default_printer(),
            'bytes': len(tspl_str),
        })
    except Exception as e:
        logger.error(f'Raw TSPL route error: {e}')
        return jsonify({'error': str(e)}), 500


def build_tspl_cut_label(
    position='',
    bar_info='',
    profile_name='',
    profile_ref='',
    cut_name='',
    finishing='',
    length=0,
    angles='',
    quantity=1,
    bin_number=0,
    shop_name='',
    label_width_mm=45,
    label_height_mm=35,
    order_ref='',
    source='',
):
    """Build TSPL commands for a single cut label (thermal printer).

    Default label: 45×35mm landscape (360×280 dots @ 203 DPI).

    8 fields:
      1. profile_ref   e.g. "2RF21 18820"
      2. bin_number    e.g. 3
      3. length        e.g. 1200
      4. profile_name  e.g. "H" or "L"  (H=horizontal, L=vertical)
      5. position      e.g. "Ch 1 ET2"
      6. finishing     e.g. "RAL 7024M"
      7. order_ref     e.g. "#1245"
      8. angles        e.g. "45/45"

    Font tiers:
      HUGE  — Font 5, scale 2×2 or 1×2 : length  + profile_name tag (same scale)
      BIG   — Font 5, scale 1×1 (32×48): bin_number (same font, smaller scale)
      MED   — Font 3, 1×1 (16×24)      : profile_ref
      SMALL — Font 2, 1×1 (12×20)      : position · finishing · angles · OF#
      TINY  — Font 1, 1×1 (8×12)       : footer text

    Layout (45×35mm = 360×280 dots):
      ┌──────────────────────────────────────┐
      │ 2RF21 18820  [MED]          │  3[BIG]│  ← profile ref | bin#
      ├─────────────────────────────┘        │
      │         1200 H           [HUGE]      │  ← length + H/L tag (centered)
      ├──────────────────────────────────────┤
      │ Ch1ET2  RAL7024M  45/45  #1245[SMALL]│  ← pos·fin·angles·OF
      │      By PrintBridge          [TINY]  │  ← footer
      └──────────────────────────────────────┘
    """
    logger.debug(
        f'[build_tspl_cut_label] profile_name={profile_name!r} profile_ref={profile_ref!r} '
        f'cut_name={cut_name!r} length={length} angles={angles!r} '
        f'position={position!r} bar_info={bar_info!r} finishing={finishing!r} '
        f'bin_number={bin_number} order_ref={order_ref!r} label={label_width_mm}x{label_height_mm}mm'
    )

    dpmm = 8  # 203 DPI = 8 dots/mm
    w = label_width_mm * dpmm   # 45*8 = 360
    h = label_height_mm * dpmm  # 35*8 = 280

    # ── Sanitise text fields ──
    s_ref       = _safe_text(profile_ref, 22) if profile_ref else ''
    s_finishing = _safe_text(finishing, 16) if finishing else ''
    s_angles    = _safe_text(angles, 12) if angles and angles not in ('—', '-') else ''
    s_bin       = str(bin_number) if bin_number else ''
    s_length    = str(length) if length else ''
    s_cut_name  = _safe_text(cut_name, 4) if cut_name else ''  # e.g. 'H' or 'L'
    # item_measurement position — on chutes show today's date instead
    if source == 'waste':
        from datetime import date
        s_position = date.today().strftime('%d/%m/%Y')
    else:
        s_position  = _safe_text(str(position), 16) if position else ''
    # bar/coupe info (e.g. "Barre 1 — Coupe 3") — strip to short form for detail row
    raw_bar = str(bar_info) if bar_info else ''
    if ' — ' in raw_bar:
        raw_bar = raw_bar.split(' — ', 1)[1]  # e.g. "Coupe 3" or "Chute"
    s_bar_info  = _safe_text(raw_bar, 10) if raw_bar else ''
    s_order     = _safe_text(f'OF#{order_ref}', 10) if order_ref else ''

    cmds = [
        f'SIZE {label_width_mm} mm, {label_height_mm} mm',
        'GAP 2 mm, 0 mm',
        'DIRECTION 0',
        'CLS',
    ]

    def _add(x, y, font_spec, text, mw=None):
        cmd = _tspl_text(x, y, font_spec, text, max_width=mw)
        if cmd:
            cmds.append(cmd)

    margin = 6
    border_thick = 3

    # ── Outer border box ──
    cmds.append(f'BOX {margin},{margin},{w - margin},{h - margin},{border_thick}')

    inner_l = margin + border_thick + 14
    inner_r = w - margin - border_thick - 3
    inner_w = inner_r - inner_l

    # ── Row heights (dots) ──
    tiny_h  = 12   # Font 1 1×1
    small_h = 20   # Font 2 1×1
    med_h   = 24   # Font 3 1×1
    big_h   = 48   # Font 5 1×1 (bin#)

    # ── Top zone ──
    top_inner  = margin + border_thick + 4       # y=13
    ref_zone_h = med_h + 6                       # 30 dots
    ref_y      = top_inner + 2                   # y=15
    ref_bot    = top_inner + ref_zone_h          # y=43  (separator drawn at y=44)

    # ── Bottom-up: place rows from border upward ──
    border_bot = h - margin - border_thick       # y=274
    pad        = 6                               # inner pad from border
    footer_y    = border_bot - pad - small_h     # y=248  OF# row
    detail_y    = footer_y  - 6  - small_h       # y=222  Coupe·angles row
    finishing_y = detail_y  - 6  - small_h       # y=196  Blanc row
    pos_y       = finishing_y - 6 - med_h        # y=166  Ch1 Et2 row

    # Length zone: from separator bottom to pos_y top
    len_zone_top = ref_bot + 10                  # y=53   (10 dot gap after separator)
    len_zone_bot = pos_y - 6                     # y=160

    # ── BIG font for length: Font 5 ──
    digits = len(s_length)
    if digits <= 3:
        lsx, lsy = 2, 2          # char 64×96 dots
    elif digits == 4:
        lsx, lsy = 1, 2          # char 32×96 dots
    else:
        lsx, lsy = 1, 1          # fallback
    len_char_w = 32 * lsx
    len_char_h = 48 * lsy
    len_text_w = digits * len_char_w

    # ── Row 1: profile ref (MED Font3, left) + bin# (Font5 1×1, right) ──
    bin_zone_w = 32 + 14  # Font5 1×1 = 32 dots + padding
    divider_x  = inner_r - bin_zone_w
    cmds.append(f'BAR {divider_x},{top_inner},{2},{ref_zone_h}')

    if s_ref:
        _add(inner_l, ref_y, '"3",0,1,1', s_ref, mw=divider_x - inner_l - 4)

    if s_bin:
        bin_cx = divider_x + 7
        bin_cy = top_inner + max(0, (ref_zone_h - big_h) // 2)
        cmds.append(f'TEXT {bin_cx},{bin_cy},"5",0,1,1,"{s_bin}"')

    # ── Thin horizontal separator below ref row ──
    cmds.append(f'BAR {inner_l},{ref_bot + 1},{inner_r - inner_l},{2}')

    # ── Length (centered in length zone) + cut_name tag ──
    if s_length:
        gap = 32  # dots between length number and H/L tag
        tag_w = (gap + len(s_cut_name) * len_char_w) if s_cut_name else 0
        total_text_w = len_text_w + tag_w
        cx = max(inner_l, inner_l + (inner_w - total_text_w) // 2)
        cy = len_zone_top  # pin to top — no bottom margin wasted
        cmds.append(f'TEXT {cx},{cy},"5",0,{lsx},{lsy},"{s_length}"')
        if s_cut_name:
            tag_x = cx + len_text_w + gap
            cmds.append(f'TEXT {tag_x},{cy},"5",0,{lsx},{lsy},"{s_cut_name}"')

    # ── Position (itemIndex) — Font3 1×1 (same as profile ref), centered ──
    if s_position:
        pos_text_w = len(s_position) * 16  # Font3 1×1 ≈ 16 dots/char
        pos_cx = max(inner_l, inner_l + (inner_w - pos_text_w) // 2)
        _add(pos_cx, pos_y, '"3",0,1,1', s_position)

    # ── Finishing — Font2, centered ──
    if s_finishing:
        fin_text_w = len(s_finishing) * 12
        fin_cx = max(inner_l, inner_l + (inner_w - fin_text_w) // 2)
        _add(fin_cx, finishing_y, '"2",0,1,1', s_finishing)

    # ── Detail row (Font2): bar_info · angles ──
    detail_parts = [p for p in [s_bar_info, s_angles] if p]
    s_detail = '  '.join(detail_parts)
    if s_detail:
        _add(inner_l, detail_y, '"2",0,1,1', s_detail, mw=inner_w)

    # ── Footer row: OF# Font2 (left) then footer text Font1 right after ──
    s_footer = f'By {FOOTER_TEXT}'
    footer_offset = (small_h - tiny_h) // 2  # vertically align Font1 with Font2 baseline
    if s_order:
        _add(inner_l, footer_y, '"2",0,1,1', s_order)
        footer_text_w = len(s_footer) * 8   # Font1 1×1 ≈ 8 dots/char
        footer_rx = inner_r - footer_text_w
        _add(max(inner_l, footer_rx), footer_y + footer_offset, '"1",0,1,1', s_footer)
    else:
        footer_text_w = len(s_footer) * 8
        footer_cx = max(inner_l, inner_l + (inner_w - footer_text_w) // 2)
        _add(footer_cx, footer_y + footer_offset, '"1",0,1,1', s_footer)

    cmds.append('PRINT 1')

    # Build output as bytes
    output = bytearray()
    for item in cmds:
        if isinstance(item, bytes):
            output.extend(item)
        else:
            output.extend(item.encode('ascii', errors='replace'))
        output.extend(b'\r\n')
    return bytes(output)


@app.route('/api/print-cut-labels', methods=['POST'])
def print_cut_labels_route():
    """Print cut labels using native TSPL commands (no PDF)."""
    try:
        data = request.get_json()
        logger.debug(f'[print-cut-labels] raw request JSON keys: {list(data.keys()) if data else None}')

        if not data or 'labels' not in data:
            return jsonify({'error': 'Missing "labels" array'}), 400

        labels = data['labels']
        if not isinstance(labels, list) or len(labels) == 0:
            return jsonify({'error': '"labels" must be a non-empty array'}), 400

        printer_name = data.get('printer', None)
        label_width = int(data.get('labelWidth', 45))
        label_height = int(data.get('labelHeight', 35))
        shop_name = data.get('shopName', '')
        order_ref = data.get('orderRef', '')
        copies = int(data.get('copies', 1))

        logger.info(f'[print-cut-labels] {len(labels)} labels, printer={printer_name!r}, {label_width}x{label_height}mm, copies={copies}, orderRef={order_ref!r}')

        if copies < 1 or copies > 99:
            return jsonify({'error': 'Copies must be between 1 and 99'}), 400

        all_commands = []
        total_labels = 0

        for i, label in enumerate(labels):
            logger.debug(f'[print-cut-labels] label[{i}]: {label}')
            for copy_n in range(copies):
                try:
                    tspl = build_tspl_cut_label(
                        position=label.get('position', ''),
                        bar_info=label.get('barInfo', ''),
                        profile_name=label.get('profileName', ''),
                        profile_ref=label.get('profileRef', ''),
                        cut_name=label.get('cutName', ''),
                        finishing=label.get('finishing', ''),
                        length=int(label.get('length', 0)),
                        angles=label.get('angles', ''),
                        quantity=1,
                        bin_number=int(label.get('binNumber', 0)),
                        shop_name=shop_name,
                        label_width_mm=label_width,
                        label_height_mm=label_height,
                        order_ref=order_ref,
                        source=label.get('source', ''),
                    )
                    logger.debug(f'[print-cut-labels] label[{i}] copy={copy_n+1} TSPL={len(tspl)} bytes')
                    all_commands.append(tspl)
                    total_labels += 1
                except Exception as build_err:
                    logger.error(f'[print-cut-labels] label[{i}] build failed: {build_err}', exc_info=True)
                    raise

        batch = b''.join(all_commands)
        logger.info(f'[print-cut-labels] batch ready: {total_labels} labels, {len(batch)} bytes total')

        # Save debug dump of the TSPL batch
        try:
            debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_cut_labels.tspl')
            with open(debug_path, 'wb') as f:
                f.write(batch)
            logger.debug(f'[print-cut-labels] TSPL batch saved to {debug_path}')
        except Exception as dump_err:
            logger.warning(f'[print-cut-labels] could not save debug dump: {dump_err}')

        send_tspl_raw(batch, printer_name)

        logger.info(f'[print-cut-labels] done — {total_labels} labels sent to {printer_name!r}')
        return jsonify({
            'success': True,
            'printer': printer_name or get_default_printer(),
            'totalLabels': total_labels,
            'method': 'tspl',
        })

    except Exception as e:
        logger.error(f'[print-cut-labels] route error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/print-labels', methods=['POST'])
def print_labels_route():
    """Print product labels using native TSPL commands (no PDF)."""
    try:
        data = request.get_json()
        if not data or 'labels' not in data:
            return jsonify({'error': 'Missing "labels" array'}), 400

        labels = data['labels']
        if not isinstance(labels, list) or len(labels) == 0:
            return jsonify({'error': '"labels" must be a non-empty array'}), 400

        printer_name = data.get('printer', None)
        label_width = int(data.get('labelWidth', 100))
        label_height = int(data.get('labelHeight', 150))
        shop_name = data.get('shopName', '')
        work_order_id = data.get('workOrderId', 0)
        qr_base_url = data.get('qrBaseUrl', '')
        copies = int(data.get('copies', 1))
        display_options = data.get('displayOptions', {})
        logger.info(f'Display options received: {display_options}')

        if copies < 1 or copies > 99:
            return jsonify({'error': 'Copies must be between 1 and 99'}), 400

        # Build TSPL for all labels, expanded by quantity
        all_commands = []
        total_labels = 0

        for label in labels:
            qty = int(label.get('quantity', 1))
            measurement_id = label.get('measurementId', '')
            sig = label.get('sig', '')

            # Build QR URL (truncate sig to 16 chars for smaller QR code)
            qr_url = ''
            if qr_base_url and measurement_id:
                qr_url = f'{qr_base_url}{measurement_id}'
                if sig:
                    qr_url += f'?sig={sig[:16]}'

            for _ in range(qty):
                for _ in range(copies):
                    tspl = build_tspl_label(
                        product_name=label.get('productName', 'Produit'),
                        formule_name=label.get('formuleName', ''),
                        width=label.get('width', 0),
                        height=label.get('height', 0),
                        position=label.get('position', ''),
                        quantity=qty,
                        order_ref=label.get('orderRef', ''),
                        client_name=label.get('clientName', ''),
                        qr_url=qr_url,
                        shop_name=shop_name,
                        work_order_id=work_order_id,
                        label_width_mm=label_width,
                        label_height_mm=label_height,
                        display_options=display_options,
                    )
                    all_commands.append(tspl)
                    total_labels += 1

        # Send all labels in one batch (bytes)
        # Note: each label from build_tspl_label() already ends with \r\n,
        # so we concatenate directly (no extra separator needed).
        batch = b''.join(all_commands)

        # DEBUG: dump TSPL to file and log for troubleshooting
        logger.info(f'TSPL batch: {total_labels} labels, {len(batch)} bytes')
        try:
            debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_tspl.bin')
            with open(debug_path, 'wb') as f:
                f.write(batch)
            logger.info(f'TSPL debug saved to {debug_path}')
        except Exception as e:
            logger.warning(f'Could not save debug TSPL: {e}')

        send_tspl_raw(batch, printer_name)

        return jsonify({
            'success': True,
            'printer': printer_name or get_default_printer(),
            'totalLabels': total_labels,
            'method': 'tspl',
        })

    except Exception as e:
        logger.error(f'Print labels route error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── System Tray ──────────────────────────────────────────────────────

def get_icon_path():
    """Get the path to the tray icon."""
    if getattr(sys, 'frozen', False):
        # Running as packaged app
        base = sys._MEIPASS  # type: ignore
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'icon.png')


def run_tray():
    """Run the system tray icon (blocking)."""
    try:
        import pystray
        from PIL import Image

        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            image = Image.open(icon_path)
        else:
            # Fallback: create a simple blue circle icon
            image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            from PIL import ImageDraw
            draw = ImageDraw.Draw(image)
            draw.ellipse([4, 4, 60, 60], fill=(48, 86, 211, 255))  # #3056D3

        def on_quit(icon, item):
            icon.stop()
            os._exit(0)

        def on_open_log(icon, item):
            log_file = str(LOG_DIR / 'agent.log')
            if SYSTEM == 'Darwin':
                subprocess.Popen(['open', log_file])
            elif SYSTEM == 'Windows':
                os.startfile(log_file)  # type: ignore
            else:
                subprocess.Popen(['xdg-open', log_file])

        printer_list = get_printers()
        printer_count = len(printer_list)

        menu = pystray.Menu(
            pystray.MenuItem(f'{TRAY_NAME} v{VERSION}', None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('● Running', None, enabled=False),
            pystray.MenuItem(f'{printer_count} printer{"s" if printer_count != 1 else ""} detected', None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Printers', pystray.Menu(
                *[pystray.MenuItem(p, None, enabled=False) for p in printer_list] or
                [pystray.MenuItem('No printers found', None, enabled=False)]
            )),
            pystray.MenuItem(f'Port: {PORT}', None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('View logs', on_open_log),
            pystray.MenuItem('Quit', on_quit),
        )

        tooltip = f'{TRAY_NAME} v{VERSION} — Running ({printer_count} printer{"s" if printer_count != 1 else ""})'
        icon = pystray.Icon('printbridge', image, tooltip, menu)
        logger.info('System tray icon started')

        # On macOS, pystray needs to set up the icon with a setup callback
        # that runs after the AppKit run loop starts
        def on_setup(icon):
            icon.visible = True
            # Show a startup notification (balloon tip on Windows, notification on macOS)
            import time
            def _notify():
                time.sleep(2)  # Wait for icon to be fully visible
                try:
                    icon.notify(
                        f'Agent ready — {printer_count} printer{"s" if printer_count != 1 else ""} detected (port {PORT})',
                        TRAY_NAME
                    )
                except Exception:
                    pass  # Some platforms don't support notify
            threading.Thread(target=_notify, daemon=True).start()

        icon.run(setup=on_setup)

    except Exception as e:
        logger.warning(f'System tray not available: {e}')
        # Return — the keep_alive loop will handle staying open
        return


def run_server():
    """Run the Flask server in a background thread."""
    logger.info(f'Starting {TRAY_NAME} v{VERSION} on port {PORT}')
    logger.info(f'Platform: {SYSTEM}')
    logger.info(f'Printers: {get_printers()}')
    app.run(
        host='127.0.0.1',
        port=PORT,
        debug=False,
        use_reloader=False,
    )


def install_autostart():
    """Auto-register as a LaunchAgent (macOS) or startup entry (Windows).
    Called on every launch — safe to run multiple times."""
    try:
        if SYSTEM == 'Darwin':
            # Get the path to the running executable
            if getattr(sys, 'frozen', False):
                exe_path = os.path.realpath(sys.executable)
            else:
                exe_path = os.path.realpath(sys.argv[0])
                exe_path = f'/usr/bin/python3 {exe_path}'

            plist_name = 'com.printbridge.agent.plist'
            plist_dir = Path.home() / 'Library' / 'LaunchAgents'
            plist_dir.mkdir(parents=True, exist_ok=True)
            plist_path = plist_dir / plist_name

            # Only write if not already installed
            if not plist_path.exists():
                plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.printbridge.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>"""
                plist_path.write_text(plist_content)
                logger.info(f'Auto-start installed: {plist_path}')
            else:
                logger.info('Auto-start already configured')

        elif SYSTEM == 'Windows':
            import winreg
            if getattr(sys, 'frozen', False):
                exe_path = os.path.realpath(sys.executable)
            else:
                exe_path = f'pythonw.exe "{os.path.realpath(sys.argv[0])}"'

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run',
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, 'PrintBridge', 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            logger.info('Auto-start installed (Windows registry)')

    except Exception as e:
        logger.warning(f'Could not install auto-start: {e}')


def keep_alive():
    """Keep the process alive if tray icon exits or isn't available."""
    import time
    logger.info('Running in headless mode (no tray icon)')
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        sys.exit(0)


# ─── Single Instance Guard ────────────────────────────────────────────

_lock_handle = None  # Keep reference alive for the lifetime of the process

def ensure_single_instance():
    """Ensure only one instance of the agent is running.
    On Windows: uses a named kernel mutex.
    On macOS/Linux: uses a lock file with fcntl.
    Returns True if this is the only instance, exits otherwise.
    """
    global _lock_handle

    if SYSTEM == 'Windows':
        import ctypes
        mutex_name = 'Global\\PrintBridge_Mutex'
        kernel32 = ctypes.windll.kernel32
        _lock_handle = kernel32.CreateMutexW(None, True, mutex_name)
        ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            logger.info('Another instance is already running. Exiting.')
            sys.exit(0)
    else:
        import fcntl
        lock_path = LOG_DIR / 'agent.lock'
        try:
            _lock_handle = open(lock_path, 'w')
            fcntl.flock(_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_handle.write(str(os.getpid()))
            _lock_handle.flush()
        except (IOError, OSError):
            logger.info('Another instance is already running. Exiting.')
            sys.exit(0)


# ─── Entry Point ──────────────────────────────────────────────────────

def main():
    # Prevent multiple instances
    ensure_single_instance()

    # Auto-register for startup
    install_autostart()

    # Start Flask server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Try running tray icon in main thread (required by macOS AppKit)
    run_tray()

    # If tray exited (e.g. no display, or pystray not available),
    # keep the process alive so the Flask server keeps running
    keep_alive()


if __name__ == '__main__':
    main()


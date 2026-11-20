# PrintBridge

> Silent local printing agent for web applications — print PDFs and thermal labels from any web app to any local printer.

**English** · [中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)](#)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

PrintBridge is a lightweight local agent that runs in your system tray. Any web application can send print jobs via HTTP to `localhost`, and PrintBridge prints them silently — no dialog boxes, no user interaction required.

## Features

- **Silent PDF/SVG printing** — print PDFs, or SVGs converted to PDF, without dialogs
- **TSPL label printing** — native TSPL commands for thermal printers (TSC, Xprinter, Zebra, etc.)
- **QR codes** — generate QR codes directly in TSPL labels
- **Unicode support** — automatic bitmap rendering for non-ASCII text (Arabic, Chinese, etc.)
- **System tray icon** — runs in the background with a minimal UI
- **Auto-start** — launches on system startup (macOS LaunchAgent / Windows registry)
- **Cross-platform** — works on macOS, Windows, and Linux
- **Configurable** — customize port, CORS origins, label defaults, and branding via `config.json`
- **Raw TSPL mode** — send arbitrary TSPL commands for full control

## Quick Start

### Install from source

```bash
git clone https://github.com/AnouarSbia/printbridge.git
cd printbridge
pip install -r requirements.txt
python agent.py
```

The agent starts on `http://127.0.0.1:9120` and runs in your system tray.

### Verify it's running

```bash
curl http://127.0.0.1:9120/api/status
# {"port":9120,"platform":"Darwin","status":"ok","tspl":true,"version":"1.0.0"}
```

### Download pre-built binaries

Pre-built binaries are available on the [Releases](../../releases) page:

- **Windows**: `PrintBridge-Setup.exe` (installer) or `PrintBridge.exe` (standalone)
- **macOS**: `PrintBridge-Installer.dmg`

No Python installation required for pre-built binaries.

## API Reference

All endpoints accept and return JSON. The agent listens on `127.0.0.1` only (no external access).

### `GET /api/status`

Health check — use this to detect if the agent is running.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "platform": "Darwin",
  "port": 9120,
  "tspl": true
}
```

### `GET /api/printers`

List available system printers.

**Response:**
```json
{
  "printers": ["HP LaserJet", "Xprinter XP-350"],
  "default": "HP LaserJet"
}
```

### `POST /api/print`

Print a PDF document or an SVG document (converted to PDF) silently.

**Request:**
```json
{
  "pdf": "<base64-encoded PDF or SVG bytes>",
  "printer": "HP LaserJet",
  "copies": 1,
  "mediaWidth": 100,
  "mediaHeight": 50
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pdf` | string | Yes | Base64-encoded PDF or SVG data |
| `printer` | string | No | Printer name (default: system default) |
| `copies` | int | No | Number of copies (1-99, default: 1) |
| `mediaWidth` | number | No | Label width in mm (for thermal printers) |
| `mediaHeight` | number | No | Label height in mm (for thermal printers) |

### `POST /api/print-labels`

Print product labels using TSPL commands (thermal printers).

**Request:**
```json
{
  "labels": [
    {
      "productName": "Widget A",
      "formuleName": "Standard",
      "width": 100,
      "height": 50,
      "position": "Shelf 3",
      "quantity": 2,
      "orderRef": "#1234",
      "clientName": "John Smith",
      "measurementId": "M001",
      "sig": "abc123"
    }
  ],
  "printer": "Xprinter XP-350",
  "labelWidth": 100,
  "labelHeight": 60,
  "shopName": "My Shop",
  "workOrderId": 42,
  "qrBaseUrl": "https://example.com/label/",
  "copies": 1,
  "displayOptions": {
    "showBarcode": false,
    "showFormule": true,
    "showClient": true,
    "showOrder": true,
    "showQr": true,
    "showPosition": true,
    "showShopHeader": true,
    "fontScale": 2
  }
}
```

### `POST /api/print-cut-labels`

Print compact cut/manufacturing labels using TSPL.

**Request:**
```json
{
  "labels": [
    {
      "position": "Room 1",
      "barInfo": "Bar 1 — Cut 3",
      "profileName": "H",
      "profileRef": "2RF21",
      "cutName": "H",
      "finishing": "RAL 7024",
      "length": 1200,
      "angles": "45/45",
      "binNumber": 3,
      "source": "production"
    }
  ],
  "printer": "Xprinter XP-350",
  "labelWidth": 45,
  "labelHeight": 35,
  "orderRef": "1245",
  "copies": 1
}
```

### `POST /api/print-tspl`

Send raw TSPL commands directly to a printer. Full control for custom label formats.

**Request:**
```json
{
  "tspl": "SIZE 100 mm, 60 mm\r\nGAP 2 mm, 0 mm\r\nDIRECTION 0\r\nCLS\r\nTEXT 10,10,\"4\",0,1,1,\"Hello World\"\r\nQRCODE 400,10,M,6,A,0,\"https://example.com\"\r\nPRINT 1,1\r\n",
  "printer": "Xprinter XP-350"
}
```

You can also pass TSPL as an array of command strings:

```json
{
  "tspl": [
    "SIZE 100 mm, 60 mm",
    "GAP 2 mm, 0 mm",
    "DIRECTION 0",
    "CLS",
    "TEXT 10,10,\"4\",0,1,1,\"Hello World\"",
    "PRINT 1,1"
  ],
  "printer": null
}
```

### `POST /api/test-tspl`

Send a simple test label to verify printer connectivity.

**Request:**
```json
{
  "printer": "Xprinter XP-350",
  "labelWidth": 100,
  "labelHeight": 150
}
```

## Configuration

Edit `config.json` in the same directory as `agent.py`:

```json
{
  "port": 9120,
  "cors_origins": [
    "http://localhost:*",
    "http://127.0.0.1:*",
    "https://your-app.com"
  ],
  "log_dir": "~/.printbridge",
  "label_defaults": {
    "width_mm": 100,
    "height_mm": 150,
    "dpmm": 8,
    "gap_mm": 2
  },
  "footer_text": "PrintBridge",
  "tray_name": "PrintBridge",
  "language": "zh",
  "tcp2ws": {
    "enabled": true,
    "host": "0.0.0.0",
    "tcp_port": 9090,
    "ws_port": 8181,
    "max_tcp_clients": 100,
    "close_tcp_when_ws_down": true,
    "close_tcp_on_print_end": false,
    "f1_start_cooldown_seconds": 90,
    "request_expire_seconds": 30,
    "win_title": "激光打标软件",
    "remote_agent_enabled": true,
    "remote_agent_host": "0.0.0.0",
    "remote_agent_port": 9999,
    "remote_markers": [
      {
        "ip": "192.168.0.251",
        "port": 9999
      }
    ],
    "tcp_command_prefix": "TCP:",
    "tcp_commands": [
      "TCP:sampleCode",
      "TCP:sampleCode1",
      "TCP:sampleCode2",
      "TCP:customerCode",
      "TCP:sampleName",
      "TCP:sampleName1",
      "TCP:sampleName2",
      "TCP:companyName",
      "TCP:nextTestDate",
      "TCP:QRCodeContent"
    ],
    "esc_hotkey_interval_seconds": 8,
    "ws_response_timeout": 5,
    "ws_max_retries": 2,
    "tcp_read_timeout": 30,
    "tcp_read_buffer": 4096
  }
}
```

> **Ports**: The main HTTP port (`port`, default `9120`) is independent from the tcp2ws `tcp_port` (default `9090`) and `ws_port` (default `8181`). Do **not** reuse the same port number. Set `tcp2ws.enabled` to `false` to disable the bridge.
>
> **Logs**: the main program writes `<log_dir>/agent.log`, while tcp2ws writes its own `<log_dir>/tcp2ws.log`; the tray “View logs” menu can open both. Both logs rotate at 5 MB and keep 5 backups (`*.log.1` through `*.log.5`), so each is bounded at roughly 30 MB instead of growing forever.
>
> **Hotkeys & protocol**: `remote_markers` supports multiple remote marking computers (each runs the remote hotkey agent service); `tcp_command_prefix` and `tcp_commands` customize the TCP command prefix and command list.
>
> **Job lifecycle**: on a frontend `print_end` event the bridge immediately stops serving TCP data: in-flight requests are discarded, later TCP commands are not forwarded, and late WebSocket responses are not written back, until the next F1 starts a new job. By default `close_tcp_on_print_end=false`: after sending the ESC finish hotkey the bridge **does not close TCP connections**, so the connection is reused for the next job. Set it to `true` if TCP connections must be closed after every job. Unexpected WebSocket disconnects are still controlled by `close_tcp_when_ws_down`. `f1_start_cooldown_seconds` sets the minimum wait after `print_end` before the next F1 (default 90 seconds; use `0` to disable). If the next label starts too soon after finishing a job, the marking software may still be in its finishing state and ignore F1; this cooldown prevents alternating job failures.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTBRIDGE_PORT` | `9120` | Override the port |
| `PRINTBRIDGE_FOOTER` | `PrintBridge` | Override footer text on labels |
| `PRINTBRIDGE_TRAY_NAME` | `PrintBridge` | Override tray icon name |
| `PRINTBRIDGE_LANGUAGE` | `zh` | Override UI language (`zh` or `en`) |

### CORS

By default, PrintBridge only accepts requests from `localhost`. To allow your web app to connect, add your domain to `cors_origins` in `config.json`:

```json
{
  "cors_origins": [
    "http://localhost:*",
    "https://my-app.example.com",
    "https://*.my-app.example.com"
  ]
}
```

## Building from Source

### Prerequisites

- Python 3.10+ (SVG printing via `svg2pdf-py` requires Python 3.11+ on Windows)
- `pip install -r requirements.txt`

### Windows

```cmd
build_windows.bat
```

Produces:
- `dist\PrintBridge.exe` — standalone executable
- `PrintBridge-Setup.exe` — NSIS installer (if NSIS is installed)

#### Bundling SumatraPDF.exe (recommended)

Windows silent PDF printing uses SumatraPDF. To make the built `.exe` fully self-contained, bundle SumatraPDF into the package so target machines do not need to install it:

1. Download the official portable/standalone `SumatraPDF.exe` from the [SumatraPDF download page](https://www.sumatrapdfreader.org/download-free-pdf-viewer).
2. Copy `SumatraPDF.exe` to the project root, i.e. the same directory as `build_windows.bat` and `PrintBridge.spec`.
3. Run `build_windows.bat` again.

`build_windows.bat` automatically detects `SumatraPDF.exe` and passes it to PyInstaller with `--add-data "SumatraPDF.exe;."`. If it is missing, the build still succeeds and PrintBridge will look for a system-installed SumatraPDF at runtime.

`build_windows.bat` also bundles the `fonts/` directory automatically (`--add-data "fonts;fonts"`), so the fonts used for SVG-to-PDF conversion are embedded in the executable.

> **Note:** SumatraPDF is distributed under GPLv3. If you redistribute the built executable, make sure you comply with the GPLv3 license terms (for example, by providing the corresponding source/license information).

### macOS

```bash
./build_macos.sh
```

Produces:
- `dist/PrintBridge.app` — macOS app bundle
- `dist/PrintBridge-Installer.dmg` — DMG installer (if `create-dmg` is installed)

## How It Works

```
┌──────────────┐     HTTP/JSON      ┌───────────────┐     OS print      ┌────────────┐
│  Your Web App │ ──────────────────▶│  PrintBridge   │ ────────────────▶│  Printer    │
│  (any domain) │  localhost:9120   │  (system tray) │  lp / win32print  │  (any type) │
└──────────────┘                    └───────────────┘                   └────────────┘
```

1. Your web app sends a POST request to `http://127.0.0.1:9120/api/print` (or `/api/print-labels`, `/api/print-tspl`)
2. PrintBridge decodes the data and sends it to the specified printer
3. The document prints silently — no dialog, no user interaction

### PDF Printing

- **macOS/Linux**: Uses `lp` command with optional media size for thermal printers
- **Windows**: Uses the bundled `SumatraPDF.exe` when packaged (otherwise auto-detects an installed SumatraPDF), then falls back to PowerShell `Start-Process -Verb PrintTo`, and finally `ShellExecute`
- **SVG**: SVG payloads are converted to PDF with `svg2pdf-py` using the bundled fonts from `fonts/` (Alibaba PuHuiTi 3.0 for Chinese, Alibaba Sans for Latin; system fonts are kept as fallback), so Chinese (and other Unicode) text is rendered correctly

### TSPL Label Printing

- **macOS/Linux**: Uses `lpr -o raw` to send raw bytes
- **Windows**: Uses `win32print.WritePrinter` with `RAW` data type

## Integrating with Your Web App

### JavaScript Example

```javascript
// Check if PrintBridge is running
async function checkAgent() {
  try {
    const res = await fetch('http://127.0.0.1:9120/api/status');
    return res.ok;
  } catch {
    return false;
  }
}

// Print a PDF
async function printPdf(pdfBase64, printerName) {
  const res = await fetch('http://127.0.0.1:9120/api/print', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pdf: pdfBase64,
      printer: printerName,
      copies: 1,
    }),
  });
  return res.json();
}

// Print a custom TSPL label
async function printLabel(tsplCommands, printerName) {
  const res = await fetch('http://127.0.0.1:9120/api/print-tspl', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tspl: tsplCommands,
      printer: printerName,
    }),
  });
  return res.json();
}
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Agent won't start | Check logs: `~/.printbridge/agent.log` |
| Printer not detected | Ensure printer is installed in OS settings |
| Label is blank | Verify label dimensions match your media |
| Port 9120 in use | Change port in `config.json` or set `PRINTBRIDGE_PORT` env var |
| CORS error | Add your domain to `cors_origins` in `config.json` |
| PDF won't print on Windows | Make sure `SumatraPDF.exe` is bundled (place it in the project root and rebuild) or install [SumatraPDF](https://www.sumatrapdfreader.org/) on the machine |
| Arabic text not rendering | Install `arabic-reshaper` and `python-bidi` (included in requirements.txt) |

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas we'd love help with:
- New printer protocols (ZPL, EPL, CPCL)
- Label template system (JSON-based or visual editor)
- Web UI for configuration
- Linux packaging (deb, rpm, AppImage)
- Unit and integration tests

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Flask](https://flask.palletsprojects.com/) — web framework
- [pystray](https://github.com/moses-palmer/pystray) — system tray icon
- [Pillow](https://python-pillow.org/) — image processing for bitmap text rendering
- [pywin32](https://github.com/mhammond/pywin32) — Windows printer access
- [SumatraPDF](https://www.sumatrapdfreader.org/) — silent PDF printing on Windows

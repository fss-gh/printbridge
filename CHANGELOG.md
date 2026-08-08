# Changelog

All notable changes to PrintBridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-08

### Added
- Silent PDF printing via HTTP API (`POST /api/print`)
- TSPL label printing for thermal printers (`POST /api/print-labels`, `POST /api/print-cut-labels`)
- Raw TSPL command endpoint (`POST /api/print-tspl`)
- Test TSPL endpoint (`POST /api/test-tspl`)
- Printer listing (`GET /api/printers`)
- Health check (`GET /api/status`)
- QR code generation in TSPL labels
- Unicode/Arabic text rendering via Pillow bitmap
- System tray icon with printer status (macOS, Windows, Linux)
- Auto-start on system boot (macOS LaunchAgent, Windows registry)
- Single-instance guard (mutex on Windows, fcntl on macOS/Linux)
- Configurable via `config.json` and environment variables
- CORS configuration for web app origins
- Windows NSIS installer with auto-start, shortcuts, and uninstaller
- macOS `.app` bundle with DMG installer
- GitHub Actions CI (Python 3.10–3.12, Ubuntu/macOS/Windows)
- MIT License
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, issue/PR templates

### Platform Support
- **macOS**: `lp` for PDF, `lpr -o raw` for TSPL, pystray menu bar icon
- **Windows**: SumatraPDF/PowerShell/ShellExecute for PDF, `win32print` for TSPL, pystray system tray
- **Linux**: `lp` for PDF, `lpr -o raw` for TSPL, pystray with xdg-open

# PrintBridge — Architecture & Code Quality Improvement Plan

> **Goal**: Transform the monolithic 1,526-line `agent.py` into a modular, tested, and contributor-friendly codebase.

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Target Architecture](#2-target-architecture)
3. [Module Breakdown](#3-module-breakdown)
4. [Testing Strategy](#4-testing-strategy)
5. [Code Quality Improvements](#5-code-quality-improvements)
6. [Refactoring Steps](#6-refactoring-steps)
7. [Timeline](#7-timeline)

---

## 1. Current State Analysis

### The problem: one file does everything

```
agent.py (1,526 lines)
├── Logging setup              (lines 30-41)
├── Flask app + CORS           (lines 43-58)
├── Printer discovery          (lines 61-109)    → get_printers, get_default_printer
├── PDF printing               (lines 111-263)   → _delayed_cleanup, _find_sumatra, print_pdf
├── API routes (PDF)           (lines 265-329)   → status, list_printers, print_route
├── TSPL text helpers          (lines 331-480)   → _is_ascii, _safe_ascii, _safe_text, _text_to_bitmap_bytes, _tspl_text
├── TSPL label builder         (lines 482-806)   → build_tspl_label
├── TSPL raw sender            (lines 808-869)   → send_tspl_raw
├── TSPL test route            (lines 871-908)   → test_tspl_route
├── TSPL cut label builder     (lines 910-1117)  → build_tspl_cut_label
├── API routes (labels)        (lines 1119-1292) → print_cut_labels_route, print_labels_route
├── System tray                (lines 1294-1454) → get_icon_path, run_tray, run_server, install_autostart, keep_alive
├── Single instance guard      (lines 1468-1500) → ensure_single_instance
└── Entry point                (lines 1504-1526) → main
```

### Issues

| Issue | Impact | Severity |
|-------|--------|----------|
| **Monolithic file** | Contributors can't find code, PRs conflict constantly | High |
| **No tests** | No way to verify changes don't break printing | High |
| **Global state** | `app`, `logger`, `CONFIG`, `SYSTEM` are module-level globals | Medium |
| **No type hints** | IDE autocomplete doesn't work, runtime errors possible | Medium |
| **Mixed concerns** | Flask routes + printing logic + tray UI + TSPL generation in one file | High |
| **Hardcoded label templates** | `build_tspl_label` has GCoupe-specific fields (`work_order_id`, `shop_name`, `formule_name`) | Medium |
| **No error types** | All errors are generic `Exception`, hard to handle specifically | Low |
| **Debug dumps in production** | `debug_tspl.bin`, `debug_cut_labels.tspl` written on every print | Low |

---

## 2. Target Architecture

```
printbridge/
├── agent.py                    ← Entry point only (20 lines)
├── config.json.example
├── requirements.txt
│
├── printbridge/                ← Main package
│   ├── __init__.py
│   ├── config.py               ← Configuration loading + defaults
│   ├── logging_setup.py        ← Logging configuration
│   │
│   ├── printers/
│   │   ├── __init__.py
│   │   ├── base.py             ← Abstract printer interface
│   │   ├── cups.py             ← macOS/Linux printer (lp, lpstat, lpr)
│   │   └── windows.py          ← Windows printer (win32print, SumatraPDF)
│   │
│   ├── printing/
│   │   ├── __init__.py
│   │   ├── pdf.py              ← PDF silent printing
│   │   └── tspl.py             ← TSPL raw sending
│   │
│   ├── tspl/
│   │   ├── __init__.py
│   │   ├── text.py             ← Text helpers (_is_ascii, _safe_text, _tspl_text)
│   │   ├── bitmap.py           ← Unicode/Arabic bitmap rendering
│   │   ├── fonts.py            ← Font size constants
│   │   ├── label_builder.py    ← Generic label builder (configurable fields)
│   │   ├── cut_label_builder.py← Cut label builder
│   │   └── templates/
│   │       ├── __init__.py
│   │       ├── base.py         ← Abstract label template
│   │       ├── product.py      ← Product label template
│   │       └── cut.py          ← Cut label template
│   │
│   ├── server/
│   │   ├── __init__.py
│   │   ├── app.py              ← Flask app factory
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── status.py       ← GET /api/status
│   │   │   ├── printers.py     ← GET /api/printers
│   │   │   ├── pdf.py          ← POST /api/print
│   │   │   ├── labels.py       ← POST /api/print-labels, POST /api/print-cut-labels
│   │   │   └── tspl.py         ← POST /api/test-tspl, POST /api/print-tspl
│   │   └── errors.py           ← Error handlers + custom exceptions
│   │
│   ├── tray/
│   │   ├── __init__.py
│   │   ├── icon.py             ← Tray icon setup
│   │   └── menu.py             ← Menu construction
│   │
│   ├── platform/
│   │   ├── __init__.py
│   │   ├── autostart.py        ← macOS LaunchAgent + Windows registry
│   │   └── single_instance.py  ← Mutex (Windows) + fcntl (Unix)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── cleanup.py          ← Temp file cleanup
│       └── pdf_validation.py   ← PDF validation helpers
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             ← Pytest fixtures (Flask test client, mock printer)
│   ├── test_config.py
│   ├── test_printers.py
│   ├── test_pdf_printing.py
│   ├── test_tspl_text.py
│   ├── test_tspl_bitmap.py
│   ├── test_label_builder.py
│   ├── test_cut_label_builder.py
│   ├── test_routes_status.py
│   ├── test_routes_printers.py
│   ├── test_routes_pdf.py
│   ├── test_routes_labels.py
│   ├── test_routes_tspl.py
│   └── test_single_instance.py
│
├── build_macos.sh
├── build_windows.bat
├── installer.nsi
├── generate_icon.py
├── com.printbridge.agent.plist
└── tspl_sender.py              ← Keep as standalone (used by frozen exe)
```

---

## 3. Module Breakdown

### `printbridge/config.py`

```python
from dataclasses import dataclass, field
from pathlib import Path
import json, os

@dataclass
class PrintBridgeConfig:
    port: int = 9120
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:*", "http://127.0.0.1:*"])
    log_dir: str = "~/.printbridge"
    footer_text: str = "PrintBridge"
    tray_name: str = "PrintBridge"
    label_defaults: dict = field(default_factory=lambda: {
        "width_mm": 100, "height_mm": 150, "dpmm": 8, "gap_mm": 2
    })

    @classmethod
    def load(cls) -> "PrintBridgeConfig":
        """Load from config.json, fall back to config.json.example, then defaults."""
        ...

    @property
    def log_path(self) -> Path:
        return Path(os.path.expanduser(self.log_dir))
```

**Why**: Replaces global `CONFIG` dict with a typed, validated dataclass. IDE autocomplete works. Impossible to misspell a config key.

### `printbridge/printers/`

```python
# base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class PrinterInfo:
    name: str
    is_default: bool = False
    status: str = "idle"  # idle, printing, error

class PrinterBackend(ABC):
    @abstractmethod
    def list_printers(self) -> list[PrinterInfo]: ...
    @abstractmethod
    def get_default_printer(self) -> str | None: ...
    @abstractmethod
    def send_raw(self, data: bytes, printer_name: str | None = None) -> bool: ...
    @abstractmethod
    def print_pdf(self, pdf_bytes: bytes, printer_name: str | None = None, copies: int = 1) -> bool: ...

# cups.py
class CupsBackend(PrinterBackend):
    """macOS/Linux printer backend using lp/lpstat/lpr."""
    ...

# windows.py
class WindowsBackend(PrinterBackend):
    """Windows printer backend using win32print + SumatraPDF."""
    ...
```

**Why**: Platform-specific code is isolated. Contributors on Linux don't need to read Windows code. Adding a new backend (e.g. CUPS direct API) is a new file, not editing a 200-line function.

### `printbridge/tspl/`

```python
# text.py
def tspl_text(x: int, y: int, font_spec: str, text: str, max_width: int | None = None) -> str | bytes | None:
    """Generate TSPL TEXT or BITMAP command. Returns str (ASCII) or bytes (bitmap) or None."""
    ...

# bitmap.py
def render_text_to_bitmap(x: int, y: int, text: str, font_size: int = 24, max_width: int | None = None) -> bytes | None:
    """Render Unicode/Arabic text as TSPL BITMAP command using Pillow."""
    ...

# label_builder.py
@dataclass
class LabelField:
    key: str
    value: str
    x: int = 0
    y: int = 0
    font_spec: str = '"4",0,1,1'
    max_width: int | None = None

class LabelBuilder:
    """Generic TSPL label builder — configurable fields, not hardcoded templates."""
    def __init__(self, width_mm: int, height_mm: int, dpmm: int = 8, gap_mm: int = 2):
        ...

    def add_text(self, field: LabelField) -> None: ...
    def add_qr(self, x: int, y: int, data: str, cell_size: int = 6) -> None: ...
    def add_bar(self, x: int, y: int, width: int, height: int) -> None: ...
    def add_box(self, x: int, y: int, x2: int, y2: int, thickness: int) -> None: ...
    def build(self) -> bytes: ...
```

**Why**: The current `build_tspl_label` has 300+ lines of hardcoded layout for a specific label type. The `LabelBuilder` class lets anyone build any label format without touching the core code. The old functions become thin wrappers or templates.

### `printbridge/server/`

```python
# app.py
def create_app(config: PrintBridgeConfig, printer_backend: PrinterBackend) -> Flask:
    """Flask app factory — creates app with configured routes."""
    app = Flask(__name__)
    CORS(app, origins=config.cors_origins)

    # Register blueprints
    from .routes.status import bp as status_bp
    from .routes.printers import bp as printers_bp
    from .routes.pdf import bp as pdf_bp
    from .routes.labels import bp as labels_bp
    from .routes.tspl import bp as tspl_bp

    app.register_blueprint(status_bp)
    app.register_blueprint(printers_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(labels_bp)
    app.register_blueprint(tspl_bp)

    # Register error handlers
    from .errors import register_error_handlers
    register_error_handlers(app)

    return app

# routes/pdf.py
bp = Blueprint('pdf', __name__)

@bp.route('/api/print', methods=['POST'])
def print_pdf_route():
    data = request.get_json()
    ...
```

**Why**: Flask app factory pattern enables testing (create test app with mock backend). Blueprints separate routes into files. No more 260 lines of routes in one file.

### `printbridge/tray/`

```python
# icon.py
def create_tray_icon(config: PrintBridgeConfig, printer_backend: PrinterBackend) -> pystray.Icon:
    """Create and return the system tray icon."""
    ...

# menu.py
def build_menu(config: PrintBridgeConfig, printer_backend: PrinterBackend) -> pystray.Menu:
    """Build the tray menu with printer list and controls."""
    ...
```

**Why**: Tray code is 160 lines mixed with server startup. Separating it makes it testable and replaceable (e.g. someone could add a Qt-based UI instead of pystray).

### `printbridge/platform/`

```python
# autostart.py
def install_autostart() -> None:
    """Register PrintBridge to start on system boot."""
    if SYSTEM == 'Darwin':
        _install_macos_launchagent()
    elif SYSTEM == 'Windows':
        _install_windows_registry()
    else:
        _install_linux_autostart()

# single_instance.py
def ensure_single_instance(log_dir: Path) -> None:
    """Exit if another instance is already running."""
    ...
```

**Why**: Platform-specific code for autostart and single-instance is isolated. Contributors can add Linux systemd support without touching the main code.

---

## 4. Testing Strategy

### Test pyramid

```
        ┌───────────┐
        │  E2E (2)  │  ← Manual: print real label on real printer
        ├───────────┤
        │ Integration│  ← Flask test client + mock printer backend
        │   (15)     │
        ├───────────┤
        │   Unit     │  ← Pure functions: TSPL builders, text helpers, config
        │   (40)     │
        └───────────┘
```

### Unit tests (no I/O, no network, no printer)

```python
# test_tspl_text.py
def test_ascii_text_returns_string():
    result = tspl_text(50, 30, '"4",0,1,1', "Hello")
    assert isinstance(result, str)
    assert 'TEXT 50,30,"4",0,1,1,"Hello"' in result

def test_arabic_text_returns_bytes():
    result = tspl_text(50, 30, '"4",0,1,1', "مرحبا")
    assert isinstance(result, bytes)
    assert result.startswith(b'BITMAP 50,30,')

def test_empty_text_returns_none():
    assert tspl_text(50, 30, '"4",0,1,1', "") is None

# test_label_builder.py
def test_label_builder_basic():
    builder = LabelBuilder(width_mm=100, height_mm=60)
    builder.add_text(LabelField(key="product", value="Widget", x=20, y=10))
    builder.add_qr(x=600, y=100, data="https://example.com/123")
    result = builder.build()
    assert b"SIZE 100 mm, 60 mm" in result
    assert b"QRCODE 600,100" in result
    assert b"PRINT 1,1" in result

# test_config.py
def test_config_defaults():
    config = PrintBridgeConfig()
    assert config.port == 9120
    assert config.footer_text == "PrintBridge"

def test_config_env_override(monkeypatch):
    monkeypatch.setenv("PRINTBRIDGE_PORT", "8080")
    config = PrintBridgeConfig.load()
    assert config.port == 8080
```

### Integration tests (Flask test client, mock printer)

```python
# conftest.py
@pytest.fixture
def mock_printer_backend():
    """Mock printer backend that records calls instead of printing."""
    backend = MagicMock(spec=PrinterBackend)
    backend.list_printers.return_value = [
        PrinterInfo(name="TestPrinter", is_default=True),
        PrinterInfo(name="Xprinter XP-350"),
    ]
    backend.get_default_printer.return_value = "TestPrinter"
    return backend

@pytest.fixture
def client(mock_printer_backend):
    config = PrintBridgeConfig()
    app = create_app(config, mock_printer_backend)
    return app.test_client()

# test_routes_status.py
def test_status_endpoint(client):
    response = client.get('/api/status')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert data['port'] == 9120

# test_routes_pdf.py
def test_print_pdf_success(client, mock_printer_backend):
    pdf_bytes = b'%PDF-1.4 test'
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    response = client.post('/api/print', json={'pdf': pdf_b64, 'copies': 1})
    assert response.status_code == 200
    mock_printer_backend.print_pdf.assert_called_once()

def test_print_pdf_invalid_base64(client):
    response = client.post('/api/print', json={'pdf': 'not-base64!!!'})
    assert response.status_code == 400

def test_print_pdf_missing_field(client):
    response = client.post('/api/print', json={})
    assert response.status_code == 400
    assert 'pdf' in response.get_json()['error'].lower()

# test_routes_labels.py
def test_print_labels_success(client, mock_printer_backend):
    response = client.post('/api/print-labels', json={
        'labels': [{'productName': 'Widget', 'quantity': 1}],
        'labelWidth': 100,
        'labelHeight': 60,
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['totalLabels'] == 1
```

### E2E tests (manual, with real printer)

```python
# test_e2e.py
"""
Manual E2E tests — run with a real thermal printer connected.

Usage:
    python -m pytest tests/test_e2e.py --run-e2e

Requires:
    - PrintBridge agent running
    - Thermal printer connected and configured
"""
@pytest.mark.skipif not os.environ.get('RUN_E2E'):
def test_real_pdf_print():
    """Print a test PDF and verify it came out of the printer."""
    ...

def test_real_tspl_label():
    """Print a test TSPL label and verify it printed correctly."""
    ...
```

### CI integration

```yaml
# .github/workflows/ci.yml (updated)
- name: Run tests
  run: |
    pip install pytest pytest-cov
    pytest tests/ --cov=printbridge --cov-report=xml --cov-report=term

- name: Upload coverage
  uses: codecov/codecov-action@v4
```

### Coverage targets

| Module | Target coverage |
|--------|----------------|
| `tspl/text.py` | 95% |
| `tspl/bitmap.py` | 80% |
| `tspl/label_builder.py` | 90% |
| `config.py` | 95% |
| `server/routes/` | 85% |
| `printers/` | 70% (hard to test without real printers) |
| `tray/` | 50% (UI code, hard to test) |
| **Overall** | **80%** |

---

## 5. Code Quality Improvements

### 5.1 Type hints everywhere

```python
# Before
def print_pdf(pdf_bytes, printer_name=None, copies=1, media_width=None, media_height=None):

# After
def print_pdf(
    pdf_bytes: bytes,
    printer_name: str | None = None,
    copies: int = 1,
    media_width: float | None = None,
    media_height: float | None = None,
) -> bool:
```

### 5.2 Custom exceptions

```python
# printbridge/server/errors.py
class PrintBridgeError(Exception):
    """Base exception for all PrintBridge errors."""
    status_code = 500

class InvalidPDFError(PrintBridgeError):
    status_code = 400

class PrinterNotFoundError(PrintBridgeError):
    status_code = 404

class PrintJobFailedError(PrintBridgeError):
    status_code = 500

class InvalidLabelDataError(PrintBridgeError):
    status_code = 400

def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(PrintBridgeError)
    def handle_printbridge_error(e: PrintBridgeError):
        return jsonify({'error': str(e)}), e.status_code
```

### 5.3 Remove debug dumps in production

```python
# Before — writes debug file on EVERY print
debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_tspl.bin')
with open(debug_path, 'wb') as f:
    f.write(batch)

# After — only when DEBUG env var is set
if os.environ.get('PRINTBRIDGE_DEBUG'):
    debug_path = config.log_path / 'debug_tspl.bin'
    debug_path.write_bytes(batch)
```

### 5.4 Remove GCoupe-specific fields from label builders

```python
# Before — hardcoded business fields
def build_tspl_label(
    product_name='Produit',
    formule_name='',        # ← GCoupe-specific
    work_order_id=0,        # ← GCoupe-specific
    shop_name='',           # ← GCoupe-specific
    ...
)

# After — generic field system
class LabelTemplate:
    """A label template defines fields and their layout."""
    fields: list[LabelField]
    layout: LabelLayout

class ProductLabelTemplate(LabelTemplate):
    """Standard product label — customizable via config."""
    ...
```

### 5.5 Linting and formatting

```ini
# setup.cfg
[flake8]
max-line-length = 120
exclude = .git,__pycache__,build,dist

[isort]
profile = black

[mypy]
python_version = 3.10
warn_return_any = True
warn_unused_configs = True
```

```toml
# pyproject.toml
[tool.black]
line-length = 120
target-version = ['py310']
```

Add to CI:
```yaml
- name: Lint
  run: |
    pip install flake8 isort black mypy
    flake8 printbridge/
    isort --check-only printbridge/
    black --check printbridge/
    mypy printbridge/
```

### 5.6 Dependency injection

```python
# Before — global state
def print_route():
    printer_name = data.get('printer', None)
    print_pdf(pdf_bytes, printer_name, copies)  # calls global functions

# After — injected backend
def create_app(config: PrintBridgeConfig, printer_backend: PrinterBackend) -> Flask:
    @app.route('/api/print', methods=['POST'])
    def print_route():
        printer_name = data.get('printer', None)
        printer_backend.print_pdf(pdf_bytes, printer_name, copies)  # mockable
```

---

## 6. Refactoring Steps

### Step 1: Create package structure (no logic changes)

- Create `printbridge/` directory with `__init__.py`
- Create all subdirectories with `__init__.py`
- Create `tests/` directory with `__init__.py`
- Add `pyproject.toml`, `setup.cfg`
- **No code moved yet** — just empty packages

### Step 2: Extract config + logging

- Move config loading to `printbridge/config.py`
- Move logging setup to `printbridge/logging_setup.py`
- Replace global `CONFIG`, `LOG_DIR`, `logger` with imports
- Write `tests/test_config.py`
- **Verify**: `python agent.py` still works

### Step 3: Extract printer backends

- Create `printbridge/printers/base.py` with `PrinterBackend` ABC
- Move `get_printers()`, `get_default_printer()` to `cups.py` / `windows.py`
- Move `print_pdf()` to `printing/pdf.py`
- Move `send_tspl_raw()` to `printing/tspl.py`
- Write `tests/test_printers.py`, `tests/test_pdf_printing.py`
- **Verify**: `python agent.py` still works

### Step 4: Extract TSPL module

- Move text helpers to `tspl/text.py`
- Move bitmap rendering to `tspl/bitmap.py`
- Move font constants to `tspl/fonts.py`
- Move `build_tspl_label()` to `tspl/label_builder.py`
- Move `build_tspl_cut_label()` to `tspl/cut_label_builder.py`
- Write `tests/test_tspl_text.py`, `tests/test_tspl_bitmap.py`, `tests/test_label_builder.py`
- **Verify**: `python agent.py` still works, labels print correctly

### Step 5: Extract Flask server

- Create Flask app factory in `server/app.py`
- Move routes to blueprints in `server/routes/`
- Add custom exceptions in `server/errors.py`
- Write integration tests for all routes
- **Verify**: `python agent.py` still works, all API endpoints respond

### Step 6: Extract tray + platform

- Move tray code to `tray/icon.py` + `tray/menu.py`
- Move autostart to `platform/autostart.py`
- Move single-instance to `platform/single_instance.py`
- **Verify**: `python agent.py` still works, tray icon appears

### Step 7: Clean up

- Remove debug dumps (gate behind env var)
- Add type hints to all functions
- Run `black`, `isort`, `flake8`, `mypy` and fix issues
- Remove `tspl_sender.py` if no longer needed (or keep for frozen exe compatibility)
- Update `build_macos.sh` and `build_windows.bat` for new structure
- Update PyInstaller `--add-data` flags
- **Verify**: Build scripts produce working binaries

### Step 8: Update CI

- Add pytest to CI workflow
- Add linting (flake8, black, isort, mypy) to CI
- Add coverage reporting (codecov)
- Add `good first issue` labels for remaining improvements

---

## 7. Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Step 1: Package structure | 1 hour | Empty packages, `pyproject.toml` |
| Step 2: Config + logging | 2 hours | `config.py`, `logging_setup.py`, tests |
| Step 3: Printer backends | 3 hours | `printers/`, `printing/`, tests |
| Step 4: TSPL module | 4 hours | `tspl/`, tests for all builders |
| Step 5: Flask server | 3 hours | `server/`, blueprint routes, integration tests |
| Step 6: Tray + platform | 2 hours | `tray/`, `platform/` |
| Step 7: Clean up | 2 hours | Type hints, linting, debug removal |
| Step 8: CI update | 1 hour | pytest + linting in CI |
| **Total** | **~18 hours** | **Modular, tested, contributor-ready codebase** |

### Priority order

If you can't do all 8 steps right now, do them in this order:

1. **Step 2** (config) — quick win, enables testing
2. **Step 4** (TSPL) — biggest file, biggest impact
3. **Step 5** (server) — enables integration tests
4. **Step 3** (printers) — isolates platform code
5. **Step 8** (CI) — locks in quality
6. **Step 6** (tray) — low risk, can wait
7. **Step 7** (cleanup) — polish
8. **Step 1** (structure) — already done by step 2

### After refactoring

```
Before:                           After:
agent.py (1,526 lines)            agent.py (20 lines — entry point only)
                                  printbridge/ (12 modules, ~150 lines each)
                                  tests/ (15 test files, 55+ test cases)
                                  80% test coverage
                                  Type hints everywhere
                                  Linting in CI
```

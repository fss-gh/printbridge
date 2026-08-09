# Contributing to PrintBridge

First off, thanks for taking the time to contribute! 🎉

This document covers everything you need to know about contributing to PrintBridge.

## Table of Contents

- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Branching Strategy](#branching-strategy)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Release Process](#release-process)
- [Areas for Contribution](#areas-for-contribution)
- [Code of Conduct](#code-of-conduct)
- [License](#license)

---

## Quick Start

### Prerequisites

- Python 3.10+
- A printer (optional — you can develop without one using mock backend)
- `pip` package manager

### Setup

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/printbridge.git
cd printbridge

# 2. Add upstream remote
git remote add upstream https://github.com/AnouarSbia/printbridge.git

# 3. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov  # for testing

# 5. Copy config template
cp config.json.example config.json

# 6. Run the agent
python agent.py
```

The agent starts on `http://127.0.0.1:9120`. Verify it's running:

```bash
curl http://127.0.0.1:9120/api/status
```

---

## Project Structure

PrintBridge uses a modular package architecture:

```
printbridge/
├── agent.py                  # Entry point (89 lines — imports from printbridge/)
├── pyproject.toml            # Package config + tool settings
├── requirements.txt          # Python dependencies
├── config.json.example       # Configuration template
│
├── printbridge/              # Main package
│   ├── __init__.py           # Version + package docstring
│   ├── config.py             # PrintBridgeConfig dataclass
│   ├── logging_setup.py      # Logging configuration
│   │
│   ├── printers/             # Printer abstraction layer
│   │   ├── base.py           # PrinterBackend ABC
│   │   ├── cups.py           # macOS/Linux backend (lp/lpr)
│   │   ├── windows.py        # Windows backend (win32print/SumatraPDF)
│   │   └── factory.py        # Platform auto-detection
│   │
│   ├── tspl/                 # TSPL label generation
│   │   ├── fonts.py          # Font size constants
│   │   ├── text.py           # Text sanitization helpers
│   │   ├── bitmap.py         # Unicode/Arabic bitmap rendering
│   │   ├── text_cmd.py       # TEXT/BITMAP auto-selection
│   │   ├── label_builder.py  # Product label builder
│   │   └── cut_label_builder.py  # Cut label builder
│   │
│   ├── server/               # Flask HTTP server
│   │   ├── app.py            # App factory (create_app)
│   │   ├── errors.py         # Custom exceptions + handlers
│   │   └── routes/           # Blueprint-based routes
│   │       ├── status.py     # GET /api/status
│   │       ├── printers.py   # GET /api/printers
│   │       ├── pdf.py        # POST /api/print
│   │       ├── labels.py     # POST /api/print-labels, /api/print-cut-labels
│   │       └── tspl.py       # POST /api/test-tspl, /api/print-tspl
│   │
│   ├── tray/                 # System tray icon
│   │   └── icon.py           # pystray setup + menu
│   │
│   └── platform/             # Platform-specific code
│       ├── autostart.py      # macOS LaunchAgent + Windows registry
│       └── single_instance.py # Mutex (Windows) + fcntl (Unix)
│
├── tests/                    # Test suite (pytest)
│   ├── conftest.py           # Fixtures (mock backend, Flask client)
│   ├── test_config.py        # Config tests
│   ├── test_tspl_text.py     # Text helper tests
│   ├── test_tspl_text_cmd.py # TSPL command tests
│   ├── test_label_builder.py # Label builder tests
│   ├── test_routes_status.py # API status/printer tests
│   ├── test_routes_pdf.py    # PDF printing API tests
│   ├── test_routes_labels.py # Label printing API tests
│   └── test_routes_tspl.py   # TSPL API tests
│
├── build_windows.bat         # Windows build (PyInstaller + NSIS)
├── build_macos.sh            # macOS build (PyInstaller + DMG)
├── installer.nsi             # NSIS installer script
├── generate_icon.py          # Tray icon generator
├── tspl_sender.py            # Standalone TSPL sender (Windows)
└── test_tspl_label.py        # Hardware TSPL test (Windows only)
```

### Key Design Principles

1. **`agent.py` is a thin entry point** — all logic lives in `printbridge/` package
2. **Printer backends are pluggable** — implement `PrinterBackend` ABC for new platforms
3. **Flask uses app factory + blueprints** — routes are testable in isolation
4. **TSPL builders are pure functions** — no side effects, easy to unit test
5. **Config is typed** — `PrintBridgeConfig` dataclass with env var overrides

---

## Development Workflow

### 1. Sync with upstream

```bash
git checkout main
git pull upstream main
```

### 2. Create a feature branch

```bash
git checkout -b feature/add-zpl-support
# or
git checkout -b fix/pdf-copies-validation
```

### 3. Make your changes

Follow the [Code Style](#code-style) guidelines. Run tests frequently:

```bash
pytest tests/ -v
```

### 4. Test with a real printer (if applicable)

```bash
# Start the agent
python agent.py

# Test endpoints
curl http://127.0.0.1:9120/api/status
curl http://127.0.0.1:9120/api/printers
curl -X POST http://127.0.0.1:9120/api/test-tspl \
  -H "Content-Type: application/json" \
  -d '{"labelWidth": 100, "labelHeight": 150}'
```

### 5. Commit with conventional messages

```bash
git commit -m "feat: add ZPL protocol support in printers/zpl.py"
```

We follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `refactor:` | Code restructuring (no behavior change) |
| `test:` | Adding/updating tests |
| `chore:` | Build, CI, tooling |
| `breaking:` | Breaking change (use `BREAKING CHANGE:` footer) |

### 6. Push and open a PR

```bash
git push origin feature/add-zpl-support
```

Open a Pull Request against `main`. Fill out the PR template completely.

---

## Testing

### Run the test suite

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=printbridge --cov-report=term-missing

# Specific module
pytest tests/test_label_builder.py -v

# Specific test
pytest tests/test_label_builder.py::test_label_builder_basic -v
```

### Writing tests

- **Unit tests** go in `tests/test_<module>.py`
- Use the fixtures in `tests/conftest.py` (`client`, `mock_printer_backend`, `config`, `valid_pdf_b64`)
- Mock the printer backend — never send real print jobs in tests
- Test edge cases: empty input, invalid data, boundary values
- Aim for >80% coverage on new code

Example test:

```python
def test_my_new_feature(client, mock_printer_backend):
    response = client.post("/api/my-endpoint", json={"data": "test"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    mock_printer_backend.send_raw.assert_called_once()
```

---

## Code Style

- **PEP 8** — use `black` and `isort` (configured in `pyproject.toml`)
- **Type hints** — required on all public functions
- **Docstrings** — Google style for all public functions and classes
- **Line length** — 120 characters max
- **Imports** — stdlib first, then third-party, then local (isort handles this)

### Before submitting a PR

```bash
# Format
black printbridge/ tests/ agent.py
isort printbridge/ tests/ agent.py

# Lint
python -m py_compile agent.py
python -m py_compile printbridge/**/*.py

# Test
pytest tests/ -v
```

---

## Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable release branch — always working |
| `develop` | Integration branch for next release (optional) |
| `feature/*` | New features (e.g., `feature/zpl-support`) |
| `fix/*` | Bug fixes (e.g., `fix/pdf-copies-overflow`) |
| `release/*` | Release preparation (e.g., `release/1.1.0`) |
| `hotfix/*` | Urgent production fixes (e.g., `hotfix/crash-on-startup`) |

### Rules

- Never commit directly to `main` — always use a PR
- Keep branches short-lived (merge within 1-2 weeks)
- Rebase onto `main` before opening a PR to avoid merge conflicts
- Delete your branch after merging

---

## Pull Request Process

### Before opening a PR

- [ ] Branch is up to date with `main` (`git rebase upstream/main`)
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Code is formatted (`black` + `isort`)
- [ ] No debug print statements or commented-out code
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated (if user-facing change)

### PR Review Criteria

Maintainers will review PRs based on:

1. **Correctness** — Does it work? Does it fix the issue?
2. **Tests** — Are there tests? Do they pass?
3. **Code quality** — Follows style guidelines, no code smells
4. **Documentation** — Docstrings, README, CHANGELOG updated
5. **Backward compatibility** — Does it break existing API?
6. **Cross-platform** — Does it work on macOS, Windows, and Linux?

### Review Process

1. **Automated checks** — CI must pass (tests + syntax on Ubuntu/macOS/Windows)
2. **Code review** — At least one maintainer must approve
3. **Discussion** — Address feedback, push fixes, re-request review
4. **Merge** — Squash-and-merge for clean history (or rebase if multiple meaningful commits)

### PR Labels

| Label | Meaning |
|-------|---------|
| `needs-review` | PR is ready for maintainer review |
| `needs-changes` | Maintainer requested changes |
| `needs-testing` | Requires testing on specific platform |
| `breaking` | Breaking change — needs version bump |
| `good first issue` | Good for new contributors |

---

## Issue Guidelines

### Bug Reports

Use the **Bug Report** template. Include:

- OS and version (macOS 14.2, Windows 11, Ubuntu 22.04)
- Python version
- PrintBridge version
- Printer model (if relevant)
- Steps to reproduce
- Expected vs actual behavior
- Log output from `~/.printbridge/agent.log`

### Feature Requests

Use the **Feature Request** template. Include:

- Problem description (what can't you do today?)
- Proposed solution (API, CLI, behavior)
- Alternatives considered
- Use case (who benefits and how?)

### Issue Labels

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | Red | Something isn't working |
| `enhancement` | Blue | New feature or improvement |
| `documentation` | Yellow | Docs improvement |
| `good first issue` | Green | Good for newcomers |
| `help wanted` | Purple | Extra attention needed |
| `question` | Gray | Further information requested |
| `wontfix` | Black | Won't be worked on |
| `duplicate` | Gray | Already reported |
| `platform:macos` | — | macOS-specific |
| `platform:windows` | — | Windows-specific |
| `platform:linux` | — | Linux-specific |
| `priority:high` | — | Urgent |
| `priority:low` | — | Nice to have |

### Issue Lifecycle

1. **Opened** — automatically labeled by GitHub Actions
2. **Triaged** — maintainer confirms/updates labels within 48h
3. **In progress** — someone is working on it (comment or self-assign)
4. **Resolved** — fixed in a PR or closed as wontfix/duplicate
5. **Stale** — no activity for 60 days → bot comments warning
6. **Closed** — no activity for 90 days → bot closes automatically

---

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0 → 2.0.0): Breaking API changes
- **MINOR** (1.0.0 → 1.1.0): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backward compatible

### Release Steps (for maintainers)

1. Update `CHANGELOG.md` with all changes since last release
2. Bump version in `printbridge/__init__.py` and `pyproject.toml`
3. Create a release branch: `git checkout -b release/v1.1.0`
4. Run full test suite: `pytest tests/ -v`
5. Test build on macOS and Windows
6. Merge to `main` and tag: `git tag v1.1.0 && git push origin v1.1.0`
7. Create GitHub Release with changelog notes
8. Attach pre-built binaries (`.exe`, `.dmg`) to the release

### Pre-release Checklist

- [ ] All tests pass on Ubuntu, macOS, Windows
- [ ] `CHANGELOG.md` updated
- [ ] Version bumped in `__init__.py` and `pyproject.toml`
- [ ] Build tested on macOS (`./build_macos.sh`)
- [ ] Build tested on Windows (`build_windows.bat`)
- [ ] No `TODO` or `FIXME` in released code
- [ ] README reflects current API

---

## Areas for Contribution

### Good First Issues

Look for issues labeled `good first issue` — these are scoped for newcomers:

- Add `--port` CLI argument
- Add `--version` CLI argument
- Add Docker support
- Add systemd service file for Linux
- Improve error messages for common failures

### Major Areas

| Area | Skills needed | Impact |
|------|---------------|--------|
| **New printer protocols** (ZPL, EPL, CPCL) | Python, thermal printer knowledge | High |
| **Label template system** | Python, JSON schema | High |
| **Web UI** for config & testing | HTML/JS, Flask | Medium |
| **Linux packaging** (deb, rpm, AppImage) | Shell, packaging tools | Medium |
| **Internationalization** | Python i18n | Low |
| **Docker support** | Docker, networking | Medium |
| **Plugin system** | Python, architecture | High |
| **Performance** | Profiling, optimization | Low |

---

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). Be respectful and welcoming to all contributors regardless of experience level.

---

## License

By contributing to PrintBridge, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

## Questions?

- Open a [Discussion](https://github.com/AnouarSbia/printbridge/discussions) for general questions
- Open an [Issue](https://github.com/AnouarSbia/printbridge/issues) for bugs and feature requests
- Tag `@AnouarSbia` in PRs that need maintainer review

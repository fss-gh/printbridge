# Contributing to PrintBridge

Thank you for your interest in contributing to PrintBridge! This document outlines the process for contributing to the project.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/AnouarSbia/printbridge.git
   cd printbridge
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Create a branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/my-feature
   ```

## Development

### Running the agent locally

```bash
python agent.py
```

The agent starts on `http://127.0.0.1:9120` by default. You can change the port in `config.json` or via the `PRINTBRIDGE_PORT` environment variable.

### Testing

Test TSPL label printing with a connected thermal printer:

```bash
python test_tspl_label.py
```

You can also test via the HTTP API:

```bash
# Check status
curl http://127.0.0.1:9120/api/status

# List printers
curl http://127.0.0.1:9120/api/printers

# Send a test TSPL label
curl -X POST http://127.0.0.1:9120/api/test-tspl \
  -H "Content-Type: application/json" \
  -d '{"printer": null, "labelWidth": 100, "labelHeight": 150}'
```

### Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) guidelines
- Use descriptive variable and function names
- Add docstrings to all public functions
- Keep functions focused and modular

### Project Structure

```
printbridge/
├── agent.py              # Main agent code (Flask server + tray icon)
├── tspl_sender.py        # Standalone TSPL sender for Windows
├── generate_icon.py      # Icon generation script
├── config.json           # Configuration file
├── requirements.txt      # Python dependencies
├── build_windows.bat     # Windows build script (PyInstaller + NSIS)
├── build_macos.sh        # macOS build script (PyInstaller + DMG)
├── installer.nsi         # NSIS installer script
├── test_tspl_label.py    # TSPL printer test script
└── com.printbridge.agent.plist  # macOS LaunchAgent plist
```

## Submitting Changes

1. **Test your changes** thoroughly
2. **Commit** with a clear message:
   ```bash
   git commit -m "Add support for Zebra ZPL protocol"
   ```
3. **Push** to your fork:
   ```bash
   git push origin feature/my-feature
   ```
4. **Open a Pull Request** on GitHub with:
   - A clear title and description
   - Reference to any related issues
   - Screenshots/logs if applicable

## Pull Request Guidelines

- One feature or bugfix per PR
- Keep changes focused and minimal
- Update documentation if needed
- Ensure code runs without errors on both macOS and Windows

## Reporting Bugs

When reporting bugs, please include:

1. **OS** (macOS / Windows / Linux)
2. **Python version**
3. **Printer model** (if relevant)
4. **Steps to reproduce**
5. **Expected vs actual behavior**
6. **Log output** (from `~/.printbridge/agent.log`)

## Feature Requests

We welcome feature requests! Please open an issue with:

- Use case description
- Proposed API or behavior
- Any relevant references

## Areas for Contribution

- **New printer protocols** (ZPL, EPL, CPCL, etc.)
- **Linux support** improvements
- **Label template system** — visual editor or JSON-based templates
- **Web UI** for configuration and testing
- **Internationalization** — tray menu translations
- **Docker support** for headless deployments
- **Tests** — unit tests, integration tests

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). Be respectful and welcoming to all contributors.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

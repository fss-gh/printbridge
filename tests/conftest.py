"""Pytest fixtures for PrintBridge tests."""

import base64
from unittest.mock import MagicMock

import pytest

from printbridge.config import PrintBridgeConfig
from printbridge.printers.base import PrinterBackend
from printbridge.server.app import create_app


@pytest.fixture
def mock_printer_backend():
    """Mock printer backend that records calls instead of printing."""
    backend = MagicMock(spec=PrinterBackend)
    backend.list_printers.return_value = ["TestPrinter", "Xprinter XP-350"]
    backend.get_default_printer.return_value = "TestPrinter"
    return backend


@pytest.fixture
def config():
    """Test configuration."""
    return PrintBridgeConfig()


@pytest.fixture
def client(mock_printer_backend, config):
    """Flask test client with mock printer backend."""
    app = create_app(config, mock_printer_backend)
    return app.test_client()


@pytest.fixture
def valid_pdf_b64():
    """Base64-encoded minimal valid PDF."""
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    return base64.b64encode(pdf_bytes).decode()

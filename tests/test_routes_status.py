"""Tests for API routes — status and printers."""

from tests.conftest import mock_printer_backend, config, client  # noqa: F401


def test_status_endpoint(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["port"] == 9120
    assert data["tspl"] is True


def test_printers_endpoint(client):
    response = client.get("/api/printers")
    assert response.status_code == 200
    data = response.get_json()
    assert "TestPrinter" in data["printers"]
    assert data["default"] == "TestPrinter"

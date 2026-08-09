"""Tests for TSPL API routes."""

from tests.conftest import mock_printer_backend, config, client  # noqa: F401


def test_test_tspl_endpoint(client, mock_printer_backend):
    response = client.post("/api/test-tspl", json={"printer": None})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["method"] == "test"
    mock_printer_backend.send_raw.assert_called_once()


def test_print_tspl_raw_string(client, mock_printer_backend):
    tspl = "SIZE 100 mm, 60 mm\r\nCLS\r\nPRINT 1,1\r\n"
    response = client.post("/api/print-tspl", json={"commands": tspl})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    mock_printer_backend.send_raw.assert_called_once()


def test_print_tspl_raw_array(client, mock_printer_backend):
    commands = ["SIZE 100 mm, 60 mm", "CLS", "PRINT 1,1"]
    response = client.post("/api/print-tspl", json={"commands": commands})
    assert response.status_code == 200
    mock_printer_backend.send_raw.assert_called_once()


def test_print_tspl_missing_commands(client):
    response = client.post("/api/print-tspl", json={})
    assert response.status_code == 400

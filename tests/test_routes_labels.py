"""Tests for label printing API routes."""

from tests.conftest import mock_printer_backend, config, client  # noqa: F401


def test_print_labels_success(client, mock_printer_backend):
    response = client.post(
        "/api/print-labels",
        json={
            "labels": [{"productName": "Widget", "quantity": 1}],
            "labelWidth": 100,
            "labelHeight": 60,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["totalLabels"] == 1
    mock_printer_backend.send_raw.assert_called_once()


def test_print_labels_missing_array(client):
    response = client.post("/api/print-labels", json={})
    assert response.status_code == 400


def test_print_labels_empty_array(client):
    response = client.post("/api/print-labels", json={"labels": []})
    assert response.status_code == 400


def test_print_cut_labels_success(client, mock_printer_backend):
    response = client.post(
        "/api/print-cut-labels",
        json={
            "labels": [{"profileRef": "2RF21", "length": 1200, "binNumber": 3}],
            "labelWidth": 45,
            "labelHeight": 35,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["totalLabels"] == 1
    mock_printer_backend.send_raw.assert_called_once()


def test_print_cut_labels_missing_array(client):
    response = client.post("/api/print-cut-labels", json={})
    assert response.status_code == 400

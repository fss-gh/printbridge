"""Tests for PDF printing API route."""

from tests.conftest import mock_printer_backend, config, client, valid_pdf_b64  # noqa: F401


def test_print_pdf_success(client, mock_printer_backend, valid_pdf_b64):
    response = client.post("/api/print", json={"pdf": valid_pdf_b64, "copies": 1})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    mock_printer_backend.print_pdf.assert_called_once()


def test_print_pdf_missing_field(client):
    response = client.post("/api/print", json={})
    assert response.status_code == 400
    assert "pdf" in response.get_json()["error"].lower()


def test_print_pdf_invalid_base64(client):
    response = client.post("/api/print", json={"pdf": "not-valid-base64!!!"})
    assert response.status_code == 400


def test_print_pdf_not_a_pdf(client):
    import base64

    fake_bytes = b"NOT A PDF"
    fake_b64 = base64.b64encode(fake_bytes).decode()
    response = client.post("/api/print", json={"pdf": fake_b64})
    assert response.status_code == 400
    assert "pdf" in response.get_json()["error"].lower()


def test_print_svg_success(client, mock_printer_backend):
    import base64

    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
  <text x="10" y="30" font-family="Microsoft YaHei, SimSun, sans-serif" font-size="12" fill="black">中文测试</text>
</svg>"""
    svg_b64 = base64.b64encode(svg.encode("utf-8")).decode()
    response = client.post("/api/print", json={"pdf": svg_b64, "copies": 1})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    mock_printer_backend.print_pdf.assert_called_once()
    args, _ = mock_printer_backend.print_pdf.call_args
    assert args[0][:5] == b"%PDF-"


def test_print_svg_invalid(client):
    import base64

    bad_svg_b64 = base64.b64encode(b"<svg>not closed").decode()
    response = client.post("/api/print", json={"pdf": bad_svg_b64})
    assert response.status_code == 400


def test_print_pdf_copies_validation(client, valid_pdf_b64):
    response = client.post("/api/print", json={"pdf": valid_pdf_b64, "copies": 0})
    assert response.status_code == 400
    response = client.post("/api/print", json={"pdf": valid_pdf_b64, "copies": 100})
    assert response.status_code == 400

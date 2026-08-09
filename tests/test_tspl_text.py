"""Tests for TSPL text helpers."""

from printbridge.tspl.text import is_ascii, safe_ascii, safe_text


def test_is_ascii_true():
    assert is_ascii("Hello") is True
    assert is_ascii("") is True
    assert is_ascii("123 ABC") is True


def test_is_ascii_false():
    assert is_ascii("مرحبا") is False
    assert is_ascii("café") is False


def test_safe_ascii_basic():
    assert safe_ascii("Hello") == "Hello"
    assert safe_ascii("") == ""


def test_safe_ascii_strips_unicode():
    result = safe_ascii("café")
    assert "é" not in result
    assert "caf" in result


def test_safe_ascii_replaces_quotes():
    assert '"' not in safe_ascii('say "hello"')
    assert "'" in safe_ascii('say "hello"')


def test_safe_ascii_max_len():
    result = safe_ascii("abcdefghij", max_len=5)
    assert len(result) == 5


def test_safe_text_keeps_unicode():
    result = safe_text("مرحبا", max_len=10)
    assert "مرحبا" in result


def test_safe_text_replaces_quotes():
    assert '"' not in safe_text('say "hi"')
    assert "'" in safe_text('say "hi"')


def test_safe_text_empty():
    assert safe_text("") == ""
    assert safe_text(None) == ""

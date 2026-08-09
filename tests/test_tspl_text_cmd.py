"""Tests for TSPL text command generation."""

from printbridge.tspl.text_cmd import tspl_text


def test_ascii_text_returns_string():
    result = tspl_text(50, 30, '"4",0,1,1', "Hello")
    assert isinstance(result, str)
    assert 'TEXT 50,30,"4",0,1,1,"Hello"' in result


def test_empty_text_returns_none():
    assert tspl_text(50, 30, '"4",0,1,1', "") is None
    assert tspl_text(50, 30, '"4",0,1,1', None) is None


def test_ascii_text_replaces_quotes():
    result = tspl_text(50, 30, '"4",0,1,1', 'say "hi"')
    assert isinstance(result, str)
    assert '"' not in result.split('"', 3)[3].rsplit('"', 1)[0] or "'" in result


def test_arabic_text_returns_bytes_or_fallback():
    result = tspl_text(50, 30, '"4",0,1,1', "مرحبا")
    # Should return bytes (bitmap) or str (ASCII fallback) but not None
    assert result is not None

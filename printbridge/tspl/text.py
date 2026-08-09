"""TSPL text helper functions."""

import unicodedata


def is_ascii(text: str) -> bool:
    """Check if text is pure ASCII (can use TSPL TEXT command)."""
    if not text:
        return True
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def safe_ascii(text: str, max_len: int = 30) -> str:
    """Convert text to safe ASCII for TSPL TEXT command."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace('"', "'")
    return ascii_text[:max_len]


def safe_text(text: str, max_len: int = 30) -> str:
    """Sanitize text for label (keep Unicode, just remove quotes and trim)."""
    if not text:
        return ""
    t = str(text).replace('"', "'")
    return t[:max_len]

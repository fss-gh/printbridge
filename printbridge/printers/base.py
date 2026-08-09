"""Abstract printer backend interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PrinterInfo:
    """Information about a discovered printer."""

    name: str
    is_default: bool = False
    status: str = "idle"


class PrinterBackend(ABC):
    """Abstract base class for platform-specific printer backends."""

    @abstractmethod
    def list_printers(self) -> list[str]:
        """Return a list of available printer names."""
        ...

    @abstractmethod
    def get_default_printer(self) -> str | None:
        """Return the name of the default printer, or None."""
        ...

    @abstractmethod
    def send_raw(self, data: bytes, printer_name: str | None = None) -> bool:
        """Send raw bytes (e.g. TSPL commands) to a printer."""
        ...

    @abstractmethod
    def print_pdf(
        self,
        pdf_bytes: bytes,
        printer_name: str | None = None,
        copies: int = 1,
        media_width: float | None = None,
        media_height: float | None = None,
    ) -> bool:
        """Print a PDF file silently."""
        ...

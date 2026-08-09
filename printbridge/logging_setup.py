"""Logging configuration for PrintBridge."""

import logging
from pathlib import Path


def setup_logging(log_dir: Path) -> logging.Logger:
    """Configure and return the PrintBridge logger.

    Args:
        log_dir: Directory where log files are stored.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "agent.log"),
            logging.StreamHandler(),
        ],
    )

    return logging.getLogger("printbridge")

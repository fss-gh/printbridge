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


def setup_tcp2ws_logging(log_dir: Path) -> logging.Logger:
    """Configure the tcp2ws logger to write to its own tcp2ws.log file.

    The tcp2ws logger is separate from the main agent logger and does not
    propagate records to agent.log.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("printbridge.tcp2ws")
    logger.setLevel(logging.DEBUG)

    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)

    handler = logging.FileHandler(log_dir / "tcp2ws.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

    return logger

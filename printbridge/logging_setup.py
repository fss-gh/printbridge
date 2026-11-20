"""Logging configuration for PrintBridge."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Keep each log file bounded so a long-running agent cannot fill the disk.
DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 5


def _rotating_file_handler(
    log_path: Path,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> RotatingFileHandler:
    """Create a UTF-8 rotating file handler."""
    return RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )


def setup_logging(
    log_dir: Path,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> logging.Logger:
    """Configure and return the PrintBridge logger.

    Args:
        log_dir: Directory where log files are stored.
        max_bytes: Rotate agent.log after it reaches this size.
        backup_count: Number of rotated agent.log files to retain.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            _rotating_file_handler(log_dir / "agent.log", max_bytes, backup_count),
            logging.StreamHandler(),
        ],
    )

    return logging.getLogger("printbridge")


def setup_tcp2ws_logging(
    log_dir: Path,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> logging.Logger:
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

    handler = _rotating_file_handler(log_dir / "tcp2ws.log", max_bytes, backup_count)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

    return logger

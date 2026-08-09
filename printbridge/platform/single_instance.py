"""Single instance guard — prevents multiple agent instances."""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("printbridge")

_lock_handle = None


def ensure_single_instance(log_dir: Path) -> None:
    """Ensure only one instance of the agent is running.

    On Windows: uses a named kernel mutex.
    On macOS/Linux: uses a lock file with fcntl.

    Args:
        log_dir: Directory for the lock file (Unix only).
    """
    global _lock_handle
    import platform

    system = platform.system()

    if system == "Windows":
        import ctypes

        mutex_name = "Global\\PrintBridge_Mutex"
        kernel32 = ctypes.windll.kernel32
        _lock_handle = kernel32.CreateMutexW(None, True, mutex_name)
        ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            logger.info("Another instance is already running. Exiting.")
            sys.exit(0)
    else:
        import fcntl

        lock_path = log_dir / "agent.lock"
        try:
            _lock_handle = open(lock_path, "w")
            fcntl.flock(_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_handle.write(str(os.getpid()))
            _lock_handle.flush()
        except (IOError, OSError):
            logger.info("Another instance is already running. Exiting.")
            sys.exit(0)

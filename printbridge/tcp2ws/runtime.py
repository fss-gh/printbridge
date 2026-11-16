"""Runtime status registry for the tcp2ws bridge.

The tray icon reads this lightweight, thread-safe status so it can show whether
the tcp2ws module is running and which ports it is using.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_STATUS: dict = {
    "configured": False,
    "enabled": False,
    "starting": False,
    "running": False,
    "error": None,
    "host": "0.0.0.0",
    "tcp_port": 9090,
    "ws_port": 8181,
    "remote_agent_enabled": True,
    "remote_agent_port": 9999,
    "remote_agent_running": False,
}


def update(**kwargs) -> None:
    """Update runtime status fields in a thread-safe way."""
    with _lock:
        _STATUS.update(kwargs)


def get_status() -> dict:
    """Return a snapshot of the runtime status."""
    with _lock:
        return dict(_STATUS)


def set_config(config) -> None:
    """Populate status from a Tcp2WsConfig.

    Only the first caller writes the config snapshot so a later tray-menu call
    does not accidentally clear a running state set by the bridge thread.
    """
    with _lock:
        if _STATUS["configured"]:
            return
        _STATUS.update(
            configured=True,
            enabled=config.enabled,
            starting=False,
            running=False,
            error=None,
            host=config.host,
            tcp_port=config.tcp_port,
            ws_port=config.ws_port,
            remote_agent_enabled=config.remote_agent_enabled,
            remote_agent_port=config.remote_agent_port,
            remote_agent_running=False,
        )

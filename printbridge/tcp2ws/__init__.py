"""TCP-to-WebSocket bridge for connecting raw TCP clients to a WebSocket frontend."""

from .bridge import Tcp2WsBridge, extract_complete_tcp_commands
from .config import Tcp2WsConfig, DEFAULT_CONFIG
from .remote_agent import create_remote_agent_server

__all__ = [
    "DEFAULT_CONFIG",
    "Tcp2WsBridge",
    "Tcp2WsConfig",
    "create_remote_agent_server",
    "extract_complete_tcp_commands",
]

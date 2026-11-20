"""Configuration dataclass for the TCP-to-WebSocket bridge.

The settings are stored in the main PrintBridge ``config.json`` under the
``tcp2ws`` section. This module only provides a typed view and validation;
it no longer reads or writes a separate tcp2ws config file.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import asdict, dataclass, field

from ..config import DEFAULT_CONFIG as _MAIN_DEFAULT_CONFIG

logger = logging.getLogger("printbridge.tcp2ws")

# The tcp2ws settings live in the main config.json's "tcp2ws" section.
DEFAULT_CONFIG = dict(_MAIN_DEFAULT_CONFIG["tcp2ws"])

_DEFAULT_REMOTE_MARKER = {"ip": "192.168.0.251", "port": 9999}


@dataclass
class Tcp2WsConfig:
    """Typed configuration for the TCP-to-WebSocket bridge."""

    enabled: bool = True
    host: str = "0.0.0.0"
    tcp_port: int = 9090
    ws_port: int = 8181
    max_tcp_clients: int = 100
    close_tcp_when_ws_down: bool = False
    close_tcp_on_print_end: bool = False
    f1_start_cooldown_seconds: int = 0
    request_expire_seconds: int = 30
    win_title: str = "激光打标软件"
    remote_agent_enabled: bool = True
    remote_agent_host: str = "0.0.0.0"
    remote_agent_port: int = 9999
    remote_markers: list = field(default_factory=lambda: [_DEFAULT_REMOTE_MARKER.copy()])
    tcp_command_prefix: str = "TCP:"
    tcp_commands: list = field(
        default_factory=lambda: [
            "TCP:sampleCode",
            "TCP:sampleCode1",
            "TCP:sampleCode2",
            "TCP:customerCode",
            "TCP:sampleName",
            "TCP:sampleName1",
            "TCP:sampleName2",
            "TCP:companyName",
            "TCP:nextTestDate",
            "TCP:QRCodeContent",
        ]
    )
    esc_hotkey_interval_seconds: int = 8
    ws_response_timeout: int = 5
    ws_max_retries: int = 2
    tcp_read_timeout: int = 30
    tcp_read_buffer: int = 4096

    @property
    def remote_marker_hosts(self) -> list[dict]:
        """Return the configured remote marker hosts (ip/port dicts)."""
        return list(self.remote_markers)

    @classmethod
    def from_dict(cls, data: dict | None = None) -> "Tcp2WsConfig":
        """Build a validated config from a plain dict (usually config.json['tcp2ws'])."""
        cfg = dict(DEFAULT_CONFIG)
        cfg["remote_markers"] = [dict(marker) for marker in DEFAULT_CONFIG["remote_markers"]]
        cfg["tcp_commands"] = list(DEFAULT_CONFIG["tcp_commands"])
        if data:
            data = dict(data)

            # Backward compatibility: old single-host keys are converted to
            # the new "remote_markers" list when the new key is missing or is
            # still the built-in default after PrintBridgeConfig merges defaults.
            legacy_ip = data.get("remote_marker_ip")
            legacy_port = data.get("remote_marker_port")
            if legacy_ip is not None or legacy_port is not None:
                if (
                    "remote_markers" not in data
                    or data["remote_markers"] == DEFAULT_CONFIG["remote_markers"]
                ):
                    data["remote_markers"] = [
                        {
                            "ip": legacy_ip or _DEFAULT_REMOTE_MARKER["ip"],
                            "port": legacy_port or _DEFAULT_REMOTE_MARKER["port"],
                        }
                    ]

            for key, value in data.items():
                if key in DEFAULT_CONFIG:
                    cfg[key] = value

        try:
            for int_key in (
                "tcp_port",
                "ws_port",
                "remote_agent_port",
                "max_tcp_clients",
                "f1_start_cooldown_seconds",
                "request_expire_seconds",
                "esc_hotkey_interval_seconds",
                "ws_response_timeout",
                "ws_max_retries",
                "tcp_read_timeout",
                "tcp_read_buffer",
            ):
                cfg[int_key] = int(cfg[int_key])

            for bool_key in (
                "enabled",
                "close_tcp_when_ws_down",
                "close_tcp_on_print_end",
                "remote_agent_enabled",
            ):
                value = cfg[bool_key]
                cfg[bool_key] = value.lower() == "true" if isinstance(value, str) else bool(value)

            for ip_key in ("host", "remote_agent_host"):
                socket.inet_aton(cfg[ip_key])

            if not (1024 < cfg["tcp_port"] <= 65535):
                raise ValueError("TCP port must be between 1025 and 65535")
            if not (1024 < cfg["ws_port"] <= 65535):
                raise ValueError("WS port must be between 1025 and 65535")
            if not (1024 < cfg["remote_agent_port"] <= 65535):
                raise ValueError("Remote agent port must be between 1025 and 65535")
            if not (5 <= cfg["request_expire_seconds"] <= 300):
                raise ValueError("Request expire seconds must be between 5 and 300")

            # Normalize remote marker hosts.
            raw_markers = cfg["remote_markers"]
            if not isinstance(raw_markers, list):
                raise ValueError("remote_markers must be a list")
            normalized_markers: list[dict] = []
            for item in raw_markers:
                if isinstance(item, str):
                    ip, port_str = item.split(":", 1)
                    port = int(port_str)
                elif isinstance(item, dict):
                    ip = str(item.get("ip", ""))
                    port = int(item.get("port", 0))
                else:
                    raise ValueError(f"Unsupported remote marker entry: {item!r}")
                socket.inet_aton(ip)
                if not (1024 < port <= 65535):
                    raise ValueError("Remote marker port must be between 1025 and 65535")
                normalized_markers.append({"ip": ip, "port": port})
            cfg["remote_markers"] = normalized_markers

            # Normalize TCP command parsing settings.
            prefix = cfg["tcp_command_prefix"]
            if not isinstance(prefix, str) or not prefix:
                raise ValueError("tcp_command_prefix must be a non-empty string")
            commands = cfg["tcp_commands"]
            if (
                not isinstance(commands, list)
                or not commands
                or not all(isinstance(cmd, str) and cmd for cmd in commands)
            ):
                raise ValueError("tcp_commands must be a non-empty list of strings")
            cfg["tcp_commands"] = list(commands)
        except Exception as e:
            logger.error(f"Invalid tcp2ws config: {e}, reverting to safe defaults")
            cfg = dict(DEFAULT_CONFIG)
            cfg["remote_markers"] = [dict(marker) for marker in DEFAULT_CONFIG["remote_markers"]]
            cfg["tcp_commands"] = list(DEFAULT_CONFIG["tcp_commands"])

        return cls(**cfg)

    def to_dict(self) -> dict:
        """Return configuration as a plain dictionary."""
        return asdict(self)

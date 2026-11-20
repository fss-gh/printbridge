"""Configuration management for PrintBridge."""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG = {
    "port": 9120,
    "cors_origins": [
        "http://localhost:*",
        "http://127.0.0.1:*",
    ],
    "log_dir": "~/.printbridge",
    "label_defaults": {
        "width_mm": 100,
        "height_mm": 150,
        "dpmm": 8,
        "gap_mm": 2,
    },
    "footer_text": "PrintBridge",
    "tray_name": "PrintBridge",
    "language": "zh",
    "tcp2ws": {
        "enabled": True,
        "host": "0.0.0.0",
        "tcp_port": 9090,
        "ws_port": 8181,
        "max_tcp_clients": 100,
        "close_tcp_when_ws_down": True,
        "close_tcp_on_print_end": False,
        "f1_start_cooldown_seconds": 90,
        "request_expire_seconds": 30,
        "win_title": "激光打标软件",
        "remote_agent_enabled": True,
        "remote_agent_host": "0.0.0.0",
        "remote_agent_port": 9999,
        "remote_markers": [
            {"ip": "192.168.0.251", "port": 9999}
        ],
        "tcp_command_prefix": "TCP:",
        "tcp_commands": [
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
        ],
        "esc_hotkey_interval_seconds": 8,
        "ws_response_timeout": 5,
        "ws_max_retries": 2,
        "tcp_read_timeout": 30,
        "tcp_read_buffer": 4096,
    },
}


def _copy_default_tcp2ws() -> dict:
    """Return a mutable deep-enough copy of the default tcp2ws section."""
    tcp2ws = dict(DEFAULT_CONFIG["tcp2ws"])
    tcp2ws["remote_markers"] = [dict(marker) for marker in tcp2ws["remote_markers"]]
    tcp2ws["tcp_commands"] = list(tcp2ws["tcp_commands"])
    return tcp2ws


def _config_file_path() -> Path:
    """Return the persistent config.json path for the current runtime mode."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.json"
    return Path(__file__).resolve().parent.parent / "config.json"


def _example_config_file_path() -> Path:
    """Return the config.json.example path (source tree only)."""
    return Path(__file__).resolve().parent.parent / "config.json.example"


@dataclass
class PrintBridgeConfig:
    """Typed configuration for PrintBridge agent."""

    port: int = 9120
    cors_origins: list = field(default_factory=lambda: ["http://localhost:*", "http://127.0.0.1:*"])
    log_dir: str = "~/.printbridge"
    label_defaults: dict = field(default_factory=lambda: {
        "width_mm": 100,
        "height_mm": 150,
        "dpmm": 8,
        "gap_mm": 2,
    })
    footer_text: str = "PrintBridge"
    tray_name: str = "PrintBridge"
    language: str = "zh"
    tcp2ws: dict = field(default_factory=_copy_default_tcp2ws)

    @classmethod
    def load(cls) -> "PrintBridgeConfig":
        """Load configuration from config.json, falling back to config.json.example,
        then to built-in defaults."""
        cfg = {**DEFAULT_CONFIG, "tcp2ws": _copy_default_tcp2ws()}
        config_path = _config_file_path()
        example_path = _example_config_file_path()

        for path in [config_path, example_path]:
            if path.exists():
                try:
                    with open(path, "r") as f:
                        user_cfg = json.load(f)
                    cfg.update(user_cfg)
                    break
                except Exception as e:
                    print(f"Warning: could not parse {path.name}: {e}")
                    break

        # Allow env var overrides
        if os.environ.get("PRINTBRIDGE_PORT"):
            cfg["port"] = int(os.environ["PRINTBRIDGE_PORT"])
        if os.environ.get("PRINTBRIDGE_FOOTER"):
            cfg["footer_text"] = os.environ["PRINTBRIDGE_FOOTER"]
        if os.environ.get("PRINTBRIDGE_TRAY_NAME"):
            cfg["tray_name"] = os.environ["PRINTBRIDGE_TRAY_NAME"]
        if os.environ.get("PRINTBRIDGE_LANGUAGE"):
            cfg["language"] = os.environ["PRINTBRIDGE_LANGUAGE"]

        # Merge tcp2ws settings with defaults so a partial "tcp2ws" section
        # in config.json does not drop the remaining built-in values.
        if isinstance(cfg.get("tcp2ws"), dict):
            cfg["tcp2ws"] = {**_copy_default_tcp2ws(), **cfg["tcp2ws"]}

        return cls(
            port=cfg["port"],
            cors_origins=cfg.get("cors_origins", DEFAULT_CONFIG["cors_origins"]),
            log_dir=cfg.get("log_dir", "~/.printbridge"),
            label_defaults=cfg.get("label_defaults", DEFAULT_CONFIG["label_defaults"]),
            footer_text=cfg.get("footer_text", "PrintBridge"),
            tray_name=cfg.get("tray_name", "PrintBridge"),
            language=cfg.get("language", "zh"),
            tcp2ws=cfg.get("tcp2ws", _copy_default_tcp2ws()),
        )

    def save(self) -> None:
        """Persist the current configuration to config.json."""
        config_path = _config_file_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "port": self.port,
            "cors_origins": self.cors_origins,
            "log_dir": self.log_dir,
            "label_defaults": self.label_defaults,
            "footer_text": self.footer_text,
            "tray_name": self.tray_name,
            "language": self.language,
            "tcp2ws": self.tcp2ws,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def log_path(self) -> Path:
        """Return the expanded log directory path."""
        return Path(os.path.expanduser(self.log_dir))

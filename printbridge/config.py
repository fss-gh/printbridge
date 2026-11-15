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
}


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

    @classmethod
    def load(cls) -> "PrintBridgeConfig":
        """Load configuration from config.json, falling back to config.json.example,
        then to built-in defaults."""
        cfg = dict(DEFAULT_CONFIG)
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

        return cls(
            port=cfg["port"],
            cors_origins=cfg.get("cors_origins", DEFAULT_CONFIG["cors_origins"]),
            log_dir=cfg.get("log_dir", "~/.printbridge"),
            label_defaults=cfg.get("label_defaults", DEFAULT_CONFIG["label_defaults"]),
            footer_text=cfg.get("footer_text", "PrintBridge"),
            tray_name=cfg.get("tray_name", "PrintBridge"),
            language=cfg.get("language", "zh"),
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
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def log_path(self) -> Path:
        """Return the expanded log directory path."""
        return Path(os.path.expanduser(self.log_dir))

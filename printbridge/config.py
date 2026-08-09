"""Configuration management for PrintBridge."""

import json
import os
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
}


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

    @classmethod
    def load(cls) -> "PrintBridgeConfig":
        """Load configuration from config.json, falling back to config.json.example,
        then to built-in defaults."""
        cfg = dict(DEFAULT_CONFIG)
        config_path = Path(__file__).parent.parent / "config.json"
        example_path = Path(__file__).parent.parent / "config.json.example"

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

        return cls(
            port=cfg["port"],
            cors_origins=cfg.get("cors_origins", DEFAULT_CONFIG["cors_origins"]),
            log_dir=cfg.get("log_dir", "~/.printbridge"),
            label_defaults=cfg.get("label_defaults", DEFAULT_CONFIG["label_defaults"]),
            footer_text=cfg.get("footer_text", "PrintBridge"),
            tray_name=cfg.get("tray_name", "PrintBridge"),
        )

    @property
    def log_path(self) -> Path:
        """Return the expanded log directory path."""
        return Path(os.path.expanduser(self.log_dir))

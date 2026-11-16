"""Tests for PrintBridge configuration."""

import os

from printbridge.config import PrintBridgeConfig


def test_config_defaults():
    config = PrintBridgeConfig()
    assert config.port == 9120
    assert config.footer_text == "PrintBridge"
    assert config.tray_name == "PrintBridge"
    assert "http://localhost:*" in config.cors_origins
    assert config.tcp2ws["remote_agent_port"] == 9999
    assert config.tcp2ws["remote_markers"] == [{"ip": "192.168.0.251", "port": 9999}]
    assert config.tcp2ws["tcp_command_prefix"] == "TCP:"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("PRINTBRIDGE_PORT", "8080")
    monkeypatch.setenv("PRINTBRIDGE_FOOTER", "MyApp")
    monkeypatch.setenv("PRINTBRIDGE_TRAY_NAME", "MyApp")
    config = PrintBridgeConfig.load()
    assert config.port == 8080
    assert config.footer_text == "MyApp"
    assert config.tray_name == "MyApp"


def test_config_log_path():
    config = PrintBridgeConfig()
    assert ".printbridge" in str(config.log_path)

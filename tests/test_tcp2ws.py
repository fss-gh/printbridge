"""Tests for the tcp2ws bridge module."""

import json

import pytest

from printbridge.config import PrintBridgeConfig
from printbridge.logging_setup import setup_tcp2ws_logging
from printbridge.tcp2ws.bridge import extract_complete_tcp_commands
from printbridge.tcp2ws.config import DEFAULT_CONFIG, Tcp2WsConfig


def test_extract_single_complete_command():
    buffer = bytearray(b"TCP:sampleCode")
    assert extract_complete_tcp_commands(buffer) == [b"TCP:sampleCode"]
    assert buffer == bytearray()


def test_extract_partial_command_is_kept():
    buffer = bytearray(b"TCP:customerCo")
    assert extract_complete_tcp_commands(buffer) == []
    assert buffer == bytearray(b"TCP:customerCo")


def test_extract_multiple_commands():
    buffer = bytearray(b"xxTCP:sampleCodeTCP:customerCodeTCP:QRCodeContent")
    commands = extract_complete_tcp_commands(buffer)
    assert commands == [b"TCP:sampleCode", b"TCP:customerCode", b"TCP:QRCodeContent"]


def test_config_defaults():
    cfg = Tcp2WsConfig()
    assert cfg.enabled is True
    assert cfg.tcp_port == DEFAULT_CONFIG["tcp_port"]
    assert cfg.ws_port == DEFAULT_CONFIG["ws_port"]
    assert cfg.close_tcp_when_ws_down is True
    assert cfg.win_title == "激光打标软件"


def test_config_from_dict_partial():
    cfg = Tcp2WsConfig.from_dict(
        {
            "tcp_port": 9001,
            "ws_port": 8001,
            "close_tcp_when_ws_down": "false",
        }
    )
    assert cfg.tcp_port == 9001
    assert cfg.ws_port == 8001
    assert cfg.close_tcp_when_ws_down is False
    assert cfg.host == DEFAULT_CONFIG["host"]


def test_config_from_dict_invalid_values_fall_back_to_defaults():
    cfg = Tcp2WsConfig.from_dict({"tcp_port": 80})
    assert cfg.tcp_port == DEFAULT_CONFIG["tcp_port"]


def test_printbridge_config_contains_tcp2ws_defaults():
    cfg = PrintBridgeConfig()
    assert cfg.tcp2ws["tcp_port"] == 9090
    assert cfg.tcp2ws["ws_port"] == 8181
    assert cfg.tcp2ws["enabled"] is True


def test_printbridge_config_load_merges_tcp2ws_section(tmp_path, monkeypatch):
    import printbridge.config as config_module

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "port": 9120,
                "tcp2ws": {
                    "tcp_port": 9100,
                    "ws_port": 8200,
                    "enabled": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "_config_file_path", lambda: config_path)
    monkeypatch.setattr(config_module, "_example_config_file_path", lambda: tmp_path / "missing.json")

    cfg = PrintBridgeConfig.load()
    assert cfg.tcp2ws["tcp_port"] == 9100
    assert cfg.tcp2ws["ws_port"] == 8200
    assert cfg.tcp2ws["enabled"] is False
    # Missing keys are filled from defaults.
    assert cfg.tcp2ws["host"] == "0.0.0.0"


def test_tcp2ws_logging_writes_to_separate_file(tmp_path):
    log_dir = tmp_path / "logs"
    logger = setup_tcp2ws_logging(log_dir)
    logger.info("tcp2ws separate log test")

    log_file = log_dir / "tcp2ws.log"
    assert log_file.exists()
    assert "tcp2ws separate log test" in log_file.read_text(encoding="utf-8")


def test_tcp2ws_logging_rotates_files(tmp_path):
    log_dir = tmp_path / "logs"
    logger = setup_tcp2ws_logging(log_dir, max_bytes=512, backup_count=2)
    for index in range(20):
        logger.info("x" * 80 + f" {index}")

    assert (log_dir / "tcp2ws.log").exists()
    assert (log_dir / "tcp2ws.log.1").exists()
    assert (log_dir / "tcp2ws.log.2").exists()
    assert not (log_dir / "tcp2ws.log.3").exists()


def test_config_from_dict_legacy_remote_keys():
    cfg = Tcp2WsConfig.from_dict(
        {
            "remote_marker_ip": "10.0.0.1",
            "remote_marker_port": 9998,
        }
    )
    assert cfg.remote_marker_hosts == [{"ip": "10.0.0.1", "port": 9998}]


def test_config_from_dict_multiple_remote_markers():
    cfg = Tcp2WsConfig.from_dict(
        {
            "remote_markers": [
                {"ip": "10.0.0.1", "port": 9998},
                {"ip": "10.0.0.2", "port": 9997},
            ]
        }
    )
    assert cfg.remote_marker_hosts == [
        {"ip": "10.0.0.1", "port": 9998},
        {"ip": "10.0.0.2", "port": 9997},
    ]


def test_config_custom_tcp_commands_and_prefix():
    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    cfg = Tcp2WsConfig.from_dict(
        {
            "tcp_command_prefix": "CMD:",
            "tcp_commands": ["CMD:foo", "CMD:bar"],
        }
    )
    bridge = Tcp2WsBridge(cfg)
    assert bridge.tcp_command_prefix == b"CMD:"
    assert bridge.tcp_commands == [b"CMD:foo", b"CMD:bar"]

    buffer = bytearray(b"xxCMD:fooCMD:bar")
    assert extract_complete_tcp_commands(
        buffer,
        prefix=bridge.tcp_command_prefix,
        commands=bridge.tcp_commands,
    ) == [b"CMD:foo", b"CMD:bar"]


def test_printbridge_config_load_legacy_remote_keys(tmp_path, monkeypatch):
    import printbridge.config as config_module

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "port": 9120,
                "tcp2ws": {
                    "remote_marker_ip": "10.0.0.1",
                    "remote_marker_port": 9998,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "_config_file_path", lambda: config_path)
    monkeypatch.setattr(config_module, "_example_config_file_path", lambda: tmp_path / "missing.json")

    cfg = PrintBridgeConfig.load()
    tcp2ws_cfg = Tcp2WsConfig.from_dict(cfg.tcp2ws)
    assert tcp2ws_cfg.remote_marker_hosts == [{"ip": "10.0.0.1", "port": 9998}]


@pytest.mark.asyncio
async def test_remote_agent_responds_success_and_invalid(monkeypatch):
    import asyncio

    import printbridge.tcp2ws.remote_agent as remote_agent_module
    from printbridge.tcp2ws.remote_agent import create_remote_agent_server

    monkeypatch.setattr(remote_agent_module, "simulate_hotkey", lambda *args, **kwargs: None)
    cfg = Tcp2WsConfig(
        remote_agent_enabled=True,
        remote_agent_host="127.0.0.1",
        remote_agent_port=0,
    )
    server = await create_remote_agent_server(cfg)
    try:
        port = server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"TRIGGER_HOTKEY_F1")
        await writer.drain()
        assert await asyncio.wait_for(reader.read(1024), timeout=5) == b"SUCCESS"
        writer.close()
        await writer.wait_closed()

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"NOT_A_COMMAND")
        await writer.drain()
        assert await asyncio.wait_for(reader.read(1024), timeout=5) == b"INVALID_COMMAND"
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()

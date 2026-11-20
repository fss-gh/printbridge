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
    assert cfg.close_tcp_on_print_end is False
    assert cfg.f1_start_cooldown_seconds == 20
    assert cfg.win_title == "激光打标软件"


def test_config_from_dict_partial():
    cfg = Tcp2WsConfig.from_dict(
        {
            "tcp_port": 9001,
            "ws_port": 8001,
            "close_tcp_when_ws_down": "false",
            "close_tcp_on_print_end": "true",
            "f1_start_cooldown_seconds": "5",
        }
    )
    assert cfg.tcp_port == 9001
    assert cfg.ws_port == 8001
    assert cfg.close_tcp_when_ws_down is False
    assert cfg.close_tcp_on_print_end is True
    assert cfg.f1_start_cooldown_seconds == 5
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("close_on_print_end", "expected_action", "expected_writer_closed"),
    [
        (False, "finish", False),
        (True, "close", True),
    ],
)
async def test_print_end_lifecycle(
    monkeypatch,
    close_on_print_end,
    expected_action,
    expected_writer_closed,
):
    import asyncio

    import printbridge.tcp2ws.bridge as bridge_module
    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    bridge = Tcp2WsBridge(Tcp2WsConfig(close_tcp_on_print_end=close_on_print_end))

    class FakeWriter:
        def __init__(self):
            self.closed = False

        def is_closing(self):
            return self.closed

        def close(self):
            self.closed = True

    writer = FakeWriter()
    bridge.active_requests["old-request"] = (writer, 0.0, None)
    actions = []

    async def fake_finish_print_job():
        actions.append("finish")

    async def fake_close_all_tcp_clients_gracefully():
        actions.append("close")
        writer.close()

    async def fake_trigger_remote_hotkey(*args, **kwargs):
        return None

    monkeypatch.setattr(bridge_module, "simulate_hotkey", lambda *args, **kwargs: None)
    monkeypatch.setattr(bridge, "trigger_remote_hotkey", fake_trigger_remote_hotkey)
    monkeypatch.setattr(bridge, "finish_print_job", fake_finish_print_job)
    monkeypatch.setattr(
        bridge,
        "close_all_tcp_clients_gracefully",
        fake_close_all_tcp_clients_gracefully,
    )

    class FakeWebSocket:
        async def __aiter__(self):
            yield json.dumps({"event": "print_end"})

    await bridge.handle_websocket(FakeWebSocket())
    if bridge.background_tasks:
        await asyncio.gather(*list(bridge.background_tasks))

    assert actions == [expected_action]
    assert writer.closed is expected_writer_closed
    assert bridge.ws_client is None
    assert bridge.accepting_requests is False
    assert "old-request" not in bridge.active_requests
    assert bridge.stale_request_ids == set()


@pytest.mark.asyncio
async def test_f1_waits_for_print_end_cooldown(monkeypatch):
    import asyncio
    import time

    import printbridge.tcp2ws.bridge as bridge_module
    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    bridge = Tcp2WsBridge(
        Tcp2WsConfig(close_tcp_when_ws_down=False, f1_start_cooldown_seconds=0.05)
    )
    bridge.last_print_end_time = time.monotonic()
    hotkey_calls = []

    def fake_simulate_hotkey(*args, **kwargs):
        hotkey_calls.append((args, kwargs))

    async def fake_trigger_remote_hotkey(*args, **kwargs):
        return None

    monkeypatch.setattr(bridge_module, "simulate_hotkey", fake_simulate_hotkey)
    monkeypatch.setattr(bridge, "trigger_remote_hotkey", fake_trigger_remote_hotkey)

    class FakeWebSocket:
        async def __aiter__(self):
            # Stay connected long enough for the delayed F1 task to run.
            await asyncio.sleep(0.2)
            if False:
                yield ""

    started = time.monotonic()
    handler = asyncio.create_task(bridge.handle_websocket(FakeWebSocket()))
    await asyncio.sleep(0.1)

    assert bridge.start_job_task is not None
    assert bridge.start_job_task.done()
    assert len(hotkey_calls) == 1
    assert hotkey_calls[0][1]["exec_f1"] is True
    assert bridge.accepting_requests is True
    assert bridge.last_print_end_time is None

    await handler
    assert time.monotonic() - started >= 0.04


@pytest.mark.asyncio
async def test_ws_close_during_cooldown_skips_f1_and_keeps_tcp(monkeypatch):
    import asyncio
    import time

    import printbridge.tcp2ws.bridge as bridge_module
    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    bridge = Tcp2WsBridge(
        Tcp2WsConfig(close_tcp_when_ws_down=True, f1_start_cooldown_seconds=10)
    )
    bridge.last_print_end_time = time.monotonic()
    hotkey_calls = []
    close_calls = []

    def fake_simulate_hotkey(*args, **kwargs):
        hotkey_calls.append((args, kwargs))

    async def fake_trigger_remote_hotkey(*args, **kwargs):
        return None

    async def fake_close_all():
        close_calls.append(True)

    monkeypatch.setattr(bridge_module, "simulate_hotkey", fake_simulate_hotkey)
    monkeypatch.setattr(bridge, "trigger_remote_hotkey", fake_trigger_remote_hotkey)
    monkeypatch.setattr(bridge, "close_all_tcp_clients_gracefully", fake_close_all)

    class FakeWebSocket:
        async def __aiter__(self):
            await asyncio.sleep(0.05)
            if False:
                yield ""

    await bridge.handle_websocket(FakeWebSocket())

    assert hotkey_calls == []
    assert close_calls == []
    assert bridge.start_job_task is None
    assert bridge.ws_client is None
    assert bridge.last_print_end_time is not None


@pytest.mark.asyncio
async def test_print_end_stops_tcp_data_service(monkeypatch):
    import asyncio

    import printbridge.tcp2ws.bridge as bridge_module
    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    bridge = Tcp2WsBridge()

    class FakeTransport:
        def is_closing(self):
            return False

    class FakeWriter:
        def __init__(self):
            self.closed = False
            self.transport = FakeTransport()

        def is_closing(self):
            return self.closed

        def close(self):
            self.closed = True

    writer = FakeWriter()
    future = asyncio.get_running_loop().create_future()
    esc_started = asyncio.Event()

    async def fake_notify_print_finished():
        # The real ESC sequence takes about 15 seconds; it must not block the
        # WebSocket loop from processing subsequent messages.
        esc_started.set()
        await asyncio.sleep(60)

    async def fake_trigger_remote_hotkey(*args, **kwargs):
        return None

    monkeypatch.setattr(bridge_module, "simulate_hotkey", lambda *args, **kwargs: None)
    monkeypatch.setattr(bridge, "trigger_remote_hotkey", fake_trigger_remote_hotkey)
    monkeypatch.setattr(bridge, "notify_print_finished", fake_notify_print_finished)

    class FakeWebSocket:
        async def __aiter__(self):
            # A request is already in flight when print_end arrives.
            bridge.active_requests["late-request"] = (writer, 0.0, future)
            yield json.dumps({"event": "print_end"})
            # Any response arriving after print_end must not reach the TCP client.
            yield json.dumps(
                {"request_id": "late-request", "seq": 1, "response": "LATE-OK"}
            )

    await bridge.handle_websocket(FakeWebSocket())
    await asyncio.sleep(0)

    assert esc_started.is_set() is True
    assert bridge.accepting_requests is False
    assert future.done() is True
    assert isinstance(future.exception(), RuntimeError)
    assert "late-request" not in bridge.active_requests
    assert writer.closed is False

    for task in list(bridge.background_tasks):
        task.cancel()
    await asyncio.gather(*bridge.background_tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_tcp_commands_dropped_after_print_end():
    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    bridge = Tcp2WsBridge(
        Tcp2WsConfig(close_tcp_when_ws_down=False, tcp_read_timeout=0.1)
    )
    bridge.accepting_requests = False

    class FakeReader:
        def __init__(self, chunks):
            self.chunks = list(chunks)

        async def read(self, size):
            return self.chunks.pop(0) if self.chunks else b""

    class FakeTransport:
        def is_closing(self):
            return False

    class FakeWriter:
        def __init__(self):
            self.closed = False
            self.written = []
            self.transport = FakeTransport()

        def get_extra_info(self, name):
            return ("127.0.0.1", 50000) if name == "peername" else None

        def is_closing(self):
            return self.closed

        def close(self):
            self.closed = True

        async def wait_closed(self):
            return None

        def write(self, data):
            self.written.append(data)

        async def drain(self):
            return None

    writer = FakeWriter()
    reader = FakeReader([b"TCP:sampleNameTCP:sampleCode2", b""])

    await bridge.handle_tcp_client(reader, writer)

    assert bridge.active_requests == {}
    assert writer.written == []


@pytest.mark.asyncio
async def test_discard_pending_requests_keeps_tcp_writer_open():
    import asyncio

    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    bridge = Tcp2WsBridge()

    class FakeWriter:
        def __init__(self):
            self.closed = False

        def is_closing(self):
            return self.closed

    writer = FakeWriter()
    future = asyncio.get_running_loop().create_future()
    bridge.active_requests["rid"] = (writer, 0.0, future)

    bridge.discard_pending_requests("print_end")

    assert "rid" not in bridge.active_requests
    assert future.done() is True
    assert isinstance(future.exception(), RuntimeError)
    assert writer.closed is False


@pytest.mark.asyncio
async def test_expired_request_keeps_tcp_writer_open():
    import asyncio

    from printbridge.tcp2ws.bridge import Tcp2WsBridge

    bridge = Tcp2WsBridge(
        Tcp2WsConfig(close_tcp_when_ws_down=False, request_expire_seconds=0)
    )

    class FakeWriter:
        def __init__(self):
            self.closed = False

        def is_closing(self):
            return self.closed

    writer = FakeWriter()
    future = asyncio.get_running_loop().create_future()
    bridge.active_requests["expired"] = (writer, 0.0, future)

    cleanup = asyncio.create_task(bridge.clean_expired_requests())
    await asyncio.sleep(0)
    cleanup.cancel()
    await asyncio.gather(cleanup, return_exceptions=True)

    assert "expired" not in bridge.active_requests
    assert isinstance(future.exception(), RuntimeError)
    assert writer.closed is False


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

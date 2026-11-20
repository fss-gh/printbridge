"""TCP-to-WebSocket bridge server.

Accepts raw TCP commands (e.g. from a marking machine) and forwards them to a
single WebSocket frontend, then relays the frontend's responses back to the
matching TCP client.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import sys
import time
import uuid
import zlib
from collections import OrderedDict
from contextlib import AsyncExitStack

from .config import Tcp2WsConfig
from .remote_agent import (
    TRIGGER_HOTKEY_ESC,
    TRIGGER_HOTKEY_F1,
    create_remote_agent_server,
)
from .runtime import update as update_runtime_status
from .windows import simulate_hotkey

logger = logging.getLogger("printbridge.tcp2ws")

try:
    from websockets.exceptions import ConnectionClosed
except ImportError:  # pragma: no cover - websockets is an optional runtime dependency
    ConnectionClosed = Exception

DEFAULT_TCP_COMMAND_PREFIX = b"TCP:"
DEFAULT_TCP_COMMANDS = [
    b"TCP:sampleCode",
    b"TCP:sampleCode1",
    b"TCP:sampleCode2",
    b"TCP:customerCode",
    b"TCP:sampleName",
    b"TCP:sampleName1",
    b"TCP:sampleName2",
    b"TCP:companyName",
    b"TCP:nextTestDate",
    b"TCP:QRCodeContent",
]
TCP_COMMAND_PREFIX = DEFAULT_TCP_COMMAND_PREFIX
TCP_COMMANDS = list(DEFAULT_TCP_COMMANDS)
MAX_TCP_COMMAND_LENGTH = max(len(cmd) for cmd in TCP_COMMANDS)


def extract_complete_tcp_commands(
    buffer: bytearray,
    prefix: bytes = TCP_COMMAND_PREFIX,
    commands: list[bytes] | None = None,
) -> list[bytes]:
    """Extract complete, ordered TCP commands from a receive buffer.

    The buffer is mutated in place: consumed bytes are removed while partial
    commands and unknown prefixes are preserved or discarded as appropriate.
    The prefix and command list can come from configuration; defaults match
    the built-in protocol.
    """
    command_list = commands if commands is not None else TCP_COMMANDS
    if not command_list:
        return []
    max_command_length = max(len(cmd) for cmd in command_list)

    found_commands: list[bytes] = []
    while True:
        start = buffer.find(prefix)
        if start == -1:
            break
        if start > 0:
            del buffer[:start]
            continue

        if len(buffer) < len(prefix):
            break

        matched_command = None
        for cmd in command_list:
            if buffer.startswith(cmd):
                tail = buffer[len(cmd):]
                if (
                    len(tail) == 0
                    or tail.startswith(prefix)
                    or prefix.startswith(tail)
                ):
                    matched_command = cmd
                    break

        if matched_command is None:
            if len(buffer) > max_command_length:
                del buffer[0]
                continue
            break

        found_commands.append(bytes(matched_command))
        del buffer[: len(matched_command)]

    return found_commands


class Tcp2WsBridge:
    """Bridge between raw TCP clients and a single WebSocket client."""

    def __init__(self, config: Tcp2WsConfig | None = None) -> None:
        self.config = config or Tcp2WsConfig.from_dict()
        self.active_requests: OrderedDict[str, tuple] = OrderedDict()
        self.ws_client = None
        # Request IDs that belonged to an older WebSocket session. They are
        # cleaned up later, but requests arriving on the new connection must
        # not be included in that cleanup.
        self.stale_request_ids: set[str] = set()
        self.background_tasks: set[asyncio.Task] = set()
        self.start_job_task: asyncio.Task | None = None
        self.last_print_end_time: float | None = None
        # After print_end the current batch is finished and the frontend data
        # pool is gone. Do not serve any further TCP commands until the next
        # F1 starts a new job.
        self.accepting_requests = True
        self.global_tcp_close_flag = False
        self.tcp_command_prefix = self.config.tcp_command_prefix.encode("utf-8")
        self.tcp_commands = [cmd.encode("utf-8") for cmd in self.config.tcp_commands]

    @staticmethod
    def is_writer_healthy(writer) -> bool:
        """Return True if an asyncio writer is still usable."""
        if not writer:
            return False
        if writer.is_closing():
            return False
        try:
            transport = writer.transport
            return bool(transport and not transport.is_closing())
        except Exception:
            return False

    def get_local_service_ip(self) -> str:
        """Return the local IP used for outbound traffic, or 0.0.0.0."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(("223.6.6.6", 80))
                return sock.getsockname()[0]
            finally:
                sock.close()
        except Exception as e:
            logger.warning(f"Failed to determine local service IP: {e}")
            return "0.0.0.0"

    @staticmethod
    def _send_remote_hotkey_command_sync(
        remote_ip: str, remote_port: int, command: str
    ) -> bool:
        """Connect to one remote hotkey agent synchronously and send a command."""
        client_socket: socket.socket | None = None
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10)
            client_socket.connect((remote_ip, remote_port))
            logger.info(f"Connected to remote hotkey agent {remote_ip}:{remote_port}, sending {command}")

            client_socket.send(command.encode("utf-8"))
            result = client_socket.recv(1024).decode("utf-8", errors="ignore")
            if result == "SUCCESS":
                logger.info(f"Remote hotkey agent {remote_ip}:{remote_port} executed {command}")
                return True
            logger.warning(f"Remote hotkey agent {remote_ip}:{remote_port} returned: {result}")
            return False
        except Exception as e:
            logger.error(f"Failed to trigger remote hotkey on {remote_ip}:{remote_port}: {e}")
            return False
        finally:
            if client_socket is not None:
                client_socket.close()

    async def _send_remote_hotkey_command(
        self, remote_ip: str, remote_port: int, command: str
    ) -> bool:
        """Send one hotkey trigger to a remote hotkey agent without blocking the loop."""
        return await asyncio.to_thread(
            self._send_remote_hotkey_command_sync, remote_ip, remote_port, command
        )

    async def trigger_remote_hotkey(
        self,
        exec_esc: bool = False,
        exec_f1: bool = False,
    ) -> None:
        """Send hotkey triggers to all configured remote marking computers."""
        markers = self.config.remote_marker_hosts
        if not markers:
            logger.warning("No remote marker hosts configured; skipping remote hotkey")
            return

        tasks = []
        for marker in markers:
            remote_ip = marker["ip"]
            remote_port = marker["port"]
            if exec_esc:
                tasks.append(
                    self._send_remote_hotkey_command(
                        remote_ip, remote_port, TRIGGER_HOTKEY_ESC
                    )
                )
            if exec_f1:
                tasks.append(
                    self._send_remote_hotkey_command(
                        remote_ip, remote_port, TRIGGER_HOTKEY_F1
                    )
                )
        if tasks:
            await asyncio.gather(*tasks)

    async def notify_print_finished(self) -> None:
        """Send the ESC sequence that tells the marking software to stop."""
        config = self.config
        logger.info("Notifying marking software with ESC hotkey (finish job)")
        await self.trigger_remote_hotkey(True, False)
        simulate_hotkey(config.win_title, exec_esc=True, exec_f1=False)
        for _ in range(6):
            await asyncio.sleep(1)
            simulate_hotkey(config.win_title, exec_esc=True, exec_f1=False)

        await asyncio.sleep(1)
        await asyncio.sleep(config.esc_hotkey_interval_seconds)
        simulate_hotkey(config.win_title, exec_esc=True, exec_f1=False)

    def discard_pending_requests(self, reason: str) -> None:
        """Fail in-flight requests without closing their TCP connections.

        This unblocks the TCP client handlers so they can read the next job's
        data on the same connection.
        """
        pending_count = len(self.active_requests)
        if pending_count:
            logger.info(f"Discarding {pending_count} pending request(s): {reason}")
        for rid, entry in list(self.active_requests.items()):
            future = entry[2] if len(entry) > 2 else None
            if future is not None and not future.done():
                future.set_exception(RuntimeError(reason))
            self.active_requests.pop(rid, None)

    async def finish_print_job(self) -> None:
        """Finish a print job without closing TCP client connections.

        The marking software keeps its TCP connection between jobs. Closing
        that connection after ``print_end`` forces it to reconnect, but the
        software does not always do so before the next F1 job starts. Keeping
        the connection alive lets the next job reuse it.
        """
        logger.info("print_end received; sending ESC while keeping TCP clients connected")
        # The batch is already finished and the frontend data pool is gone.
        # TCP data service is stopped in handle_websocket(); this task only
        # performs the ESC sequence without blocking the WebSocket loop.
        await self.notify_print_finished()

    def schedule_print_finish(self) -> None:
        """Run the ESC sequence in the background.

        The ESC sequence takes about 15 seconds. Waiting for it inside the
        WebSocket loop would stop us from reading late WS responses while the
        laser side is still requesting data after ``print_end``.
        """
        task = asyncio.create_task(self.finish_print_job())
        self.background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)

    def _on_background_task_done(self, task: asyncio.Task) -> None:
        self.background_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Background print-finish task failed: {e}")

    async def start_job_after_delay(self, websocket) -> None:
        """Start the next job after pending ESC work and the cooldown.

        This runs in the background so the WebSocket loop keeps processing
        messages while we wait. TCP data stays disabled by print_end until
        the F1 is actually sent.
        """
        try:
            if self.background_tasks:
                logger.info("Waiting for the previous ESC sequence to finish before F1")
                await asyncio.gather(
                    *list(self.background_tasks), return_exceptions=True
                )

            cooldown = self.config.f1_start_cooldown_seconds
            if cooldown > 0 and self.last_print_end_time is not None:
                remaining = cooldown - (
                    time.monotonic() - self.last_print_end_time
                )
                if remaining > 0:
                    logger.info(
                        f"Waiting {remaining:.1f}s before F1 "
                        f"(print_end cooldown {cooldown}s)"
                    )
                    await asyncio.sleep(remaining)
                self.last_print_end_time = None

            if self.ws_client is not websocket:
                logger.info("WS client changed while waiting; skipping F1")
                return

            self.accepting_requests = True
            logger.info("Notifying marking software with F1 hotkey (start job)")
            simulate_hotkey(self.config.win_title, exec_esc=False, exec_f1=True)
            await self.trigger_remote_hotkey(False, True)
        except asyncio.CancelledError:
            logger.info("Pending F1 start cancelled")
            raise
        except Exception as e:
            logger.error(f"Failed to start job after delay: {e}")

    async def close_all_tcp_clients_gracefully(self) -> None:
        """Notify the marking software, then close all active TCP clients."""
        if self.global_tcp_close_flag:
            return
        self.global_tcp_close_flag = True
        logger.info("Starting graceful shutdown of all TCP clients...")

        await self.notify_print_finished()

        tcp_clients = list(self.active_requests.items())
        for rid, entry in tcp_clients:
            writer = entry[0]
            client_id = self._client_id_from_request_id(rid)
            await asyncio.sleep(0.1)
            if not writer.is_closing():
                try:
                    writer.close()
                    await asyncio.wait_for(writer.wait_closed(), timeout=3.0)
                    logger.info(f"Closed TCP client {client_id}")
                except Exception as e:
                    logger.warning(f"Failed to close TCP client {client_id}: {e}")

        self.active_requests.clear()
        self.global_tcp_close_flag = False
        logger.info("All TCP client connections handled")

    async def clean_expired_requests(self) -> None:
        """Periodically clean expired or stale request IDs (background task)."""
        while True:
            try:
                current_time = time.time()
                expire_seconds = self.config.request_expire_seconds
                expired_ids: list[str] = []

                for rid, entry in list(self.active_requests.items()):
                    _, create_time = entry[0], entry[1]
                    if current_time - create_time > expire_seconds:
                        expired_ids.append(rid)
                        future = entry[2] if len(entry) > 2 else None
                        if future and not future.done():
                            future.set_exception(RuntimeError("request_expired"))
                        # Keep the TCP writer open: the laser side reuses this
                        # connection for the next job. Closing it on an expired
                        # request was the original cause of alternating
                        # successful/failed jobs.

                if self.stale_request_ids:
                    logger.info("WS session changed; clearing stale request IDs")
                    for rid in list(self.stale_request_ids):
                        entry = self.active_requests.pop(rid, None)
                        future = entry[2] if entry and len(entry) > 2 else None
                        if future is not None and not future.done():
                            future.set_exception(RuntimeError("stale_ws_session"))
                    self.stale_request_ids.clear()

                for rid in expired_ids:
                    self.active_requests.pop(rid, None)

                if expired_ids:
                    logger.info(f"Cleaned {len(expired_ids)} expired/invalid request IDs")

                await asyncio.sleep(5)
            except Exception as e:
                logger.warning(f"Request cleanup task error: {e}")
                await asyncio.sleep(5)

    @staticmethod
    def _client_id_from_request_id(request_id: str) -> str:
        """Extract a readable client id from a request id of the form ip:port:uuid."""
        if ":" in request_id:
            parts = request_id.split(":")
            return f"{parts[0]}:{parts[1]}"
        return "unknown"

    async def handle_tcp_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle one raw TCP client connection."""
        config = self.config
        addr = writer.get_extra_info("peername")
        if addr:
            client_id = f"{addr[0]}:{addr[1]}"
        else:
            client_id = "unknown"

        logger.info(f"TCP client connected: {client_id}")

        if self.global_tcp_close_flag:
            logger.info(f"Rejecting new TCP connection during global shutdown: {client_id}")
            writer.close()
            await writer.wait_closed()
            return

        active_for_writer = sum(1 for v in self.active_requests.values() if v[0] == writer)
        if active_for_writer >= config.max_tcp_clients:
            logger.warning(f"Rejecting TCP connection (limit {config.max_tcp_clients}): {client_id}")
            writer.close()
            await writer.wait_closed()
            return

        if not self.ws_client and config.close_tcp_when_ws_down:
            logger.error(f"WS client not connected; rejecting TCP connection: {client_id}")
            writer.close()
            await writer.wait_closed()
            return
        if not self.ws_client and not config.close_tcp_when_ws_down:
            logger.warning(f"WS client not connected; keeping TCP connection: {client_id}")

        seq_counter = 0
        recv_buffer = bytearray()
        try:
            while True:
                if self.global_tcp_close_flag:
                    logger.info(f"Global TCP shutdown requested; exiting client loop: {client_id}")
                    break

                try:
                    data = await asyncio.wait_for(
                        reader.read(config.tcp_read_buffer), timeout=config.tcp_read_timeout
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

                if not data:
                    break

                if not self.is_writer_healthy(writer):
                    logger.error(f"TCP writer became unhealthy; disconnecting: {client_id}")
                    break

                recv_buffer.extend(data)
                commands = extract_complete_tcp_commands(
                    recv_buffer,
                    prefix=self.tcp_command_prefix,
                    commands=self.tcp_commands,
                )
                if not commands:
                    continue

                for command in commands:
                    seq_counter += 1
                    payload = command.decode("utf-8", errors="ignore")
                    if not self.accepting_requests:
                        logger.warning(
                            f"print_end received; dropping TCP command "
                            f"[{payload}] seq={seq_counter}"
                        )
                        continue

                    request_id = uuid.uuid4().hex
                    future = asyncio.get_running_loop().create_future()
                    self.active_requests[request_id] = (writer, time.time(), future)

                    crc = zlib.crc32(payload.encode("utf-8")) & 0xFFFFFFFF
                    ws_message = json.dumps(
                        {
                            "request_id": request_id,
                            "seq": seq_counter,
                            "payload": payload,
                            "crc": crc,
                        }
                    )
                    logger.info(
                        f"Parsed TCP command [{payload}] id={request_id} seq={seq_counter} crc={crc}"
                    )

                    if not self.ws_client:
                        if config.close_tcp_when_ws_down:
                            logger.error(f"WS client disconnected; closing TCP connection: {client_id}")
                            break
                        logger.warning(f"WS client disconnected; dropping message: {request_id}")
                        self.active_requests.pop(request_id, None)
                        continue

                    max_retries = config.ws_max_retries
                    retry = 0
                    try:
                        while retry <= max_retries:
                            ws_session = self.ws_client
                            if ws_session is None:
                                self.active_requests.pop(request_id, None)
                                logger.error(f"WS client disconnected; request dropped: {request_id}")
                                break
                            try:
                                await ws_session.send(ws_message)
                                logger.info(
                                    f"Forwarded to WS [{len(ws_message)} bytes] "
                                    f"id={request_id} seq={seq_counter} attempt={retry + 1}"
                                )
                            except ConnectionClosed:
                                if self.ws_client is ws_session:
                                    self.ws_client = None
                                self.stale_request_ids.update(self.active_requests.keys())
                                logger.error(f"WS client connection closed: {client_id}")
                                break

                            try:
                                response = await asyncio.wait_for(
                                    future, timeout=config.ws_response_timeout
                                )
                                response_bytes = str(response).encode("utf-8")
                                if self.is_writer_healthy(writer):
                                    writer.write(response_bytes)
                                    await writer.drain()
                                    logger.info(
                                        f"Replied to TCP client [{len(response_bytes)} bytes] "
                                        f"id={request_id}"
                                    )
                                self.active_requests.pop(request_id, None)
                                break
                            except asyncio.TimeoutError:
                                retry += 1
                                if retry > max_retries:
                                    self.active_requests.pop(request_id, None)
                                    logger.error(f"Request timed out: {request_id}")
                                    break
                                logger.warning(
                                    f"WS response timeout id={request_id}, retry {retry}/{max_retries}"
                                )
                                future = asyncio.get_running_loop().create_future()
                                self.active_requests[request_id] = (writer, time.time(), future)
                                continue
                    except Exception as e:
                        logger.error(f"Failed to forward WS message ({request_id}): {e}")
                        self.active_requests.pop(request_id, None)
                        continue
        except Exception as e:
            logger.error(f"Unexpected TCP client error ({client_id}): {e}")
        finally:
            cleaned_ids: list[str] = []
            for rid, entry in list(self.active_requests.items()):
                if entry[0] == writer:
                    self.active_requests.pop(rid, None)
                    cleaned_ids.append(rid)
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
            logger.info(
                f"TCP connection finished: {client_id} (cleaned {len(cleaned_ids)} request IDs)"
            )

    async def handle_websocket(self, websocket) -> None:
        """Handle the single allowed WebSocket frontend connection."""
        if self.ws_client:
            await websocket.close(code=1008, reason="仅允许一个WS客户端连接")
            return

        self.ws_client = websocket
        # Requests left over from an older WS session can never receive a
        # response now. Fail them without closing the TCP clients so their
        # handlers are free to read the new job's data on the same socket.
        if self.active_requests:
            self.discard_pending_requests("WS session changed")
        logger.info("WS client connected (new connection)")

        config = self.config
        cooldown_remaining = 0.0
        cooldown = config.f1_start_cooldown_seconds
        if cooldown > 0 and self.last_print_end_time is not None:
            cooldown_remaining = max(
                0.0, cooldown - (time.monotonic() - self.last_print_end_time)
            )

        if self.background_tasks or cooldown_remaining > 0:
            # Do not block the WebSocket loop while waiting. Any late
            # responses from the finished batch are ignored by the
            # accepting_requests gate.
            self.start_job_task = asyncio.create_task(
                self.start_job_after_delay(websocket)
            )
        else:
            self.last_print_end_time = None
            self.accepting_requests = True
            logger.info("Notifying marking software with F1 hotkey (start job)")
            simulate_hotkey(config.win_title, exec_esc=False, exec_f1=True)
            await self.trigger_remote_hotkey(False, True)

        graceful_end_requested = False
        print_end_handled = False
        try:
            async for message in websocket:
                try:
                    if isinstance(message, bytes):
                        text = message.decode("utf-8", errors="ignore")
                    else:
                        text = message
                    msg = json.loads(text)
                except Exception:
                    logger.warning("WS message is not valid JSON; ignoring")
                    continue

                if msg.get("event") == "print_end":
                    if print_end_handled:
                        logger.info("Duplicate print_end event ignored")
                        continue
                    print_end_handled = True
                    graceful_end_requested = True
                    self.last_print_end_time = time.monotonic()
                    self.accepting_requests = False
                    # The batch is finished and the frontend data pool is gone.
                    # Fail in-flight requests without closing the TCP writers,
                    # then drop any further TCP commands until the next F1.
                    self.discard_pending_requests("print_end received")
                    if config.close_tcp_on_print_end:
                        logger.info("Received print_end event; closing TCP clients")
                        await self.close_all_tcp_clients_gracefully()
                        break
                    logger.info(
                        "Received print_end event; stopping TCP data service "
                        "until the next F1"
                    )
                    self.schedule_print_finish()
                    continue

                request_id = msg.get("request_id")
                seq = msg.get("seq")
                response = msg.get("response")
                if not request_id or response is None:
                    logger.warning("WS message missing request_id or response; ignoring")
                    continue

                if not self.accepting_requests:
                    logger.warning(
                        f"Ignoring WS response id={request_id} seq={seq}: "
                        "print_end already received"
                    )
                    continue

                logger.info(f"Received WS response id={request_id} seq={seq}")
                if request_id not in self.active_requests:
                    logger.warning(f"Unknown request id: {request_id}")
                    continue

                writer, _, future = self.active_requests[request_id]
                if not self.is_writer_healthy(writer):
                    logger.warning(f"TCP writer for request {request_id} is unhealthy; cleaning up")
                    try:
                        if not future.done():
                            future.set_exception(RuntimeError("writer_unhealthy"))
                    except Exception:
                        pass
                    self.active_requests.pop(request_id, None)
                    continue

                try:
                    if not future.done():
                        future.set_result(response)
                        logger.info(f"Response set for request {request_id}")
                except Exception as e:
                    logger.warning(f"Failed to set future: {e}")
        except ConnectionClosed as e:
            logger.info(f"WS client disconnected: {getattr(e, 'code', '?')} - {getattr(e, 'reason', '')}")
        except Exception as e:
            logger.error(f"Unexpected WebSocket error: {e}")
        finally:
            pending_start = False
            if self.ws_client is websocket:
                # Cancel a delayed F1 before shutting down TCP; otherwise it
                # could start a job after the frontend has already gone away.
                task = self.start_job_task
                self.start_job_task = None
                if task is not None and not task.done():
                    pending_start = True
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            if (
                config.close_tcp_when_ws_down
                and not graceful_end_requested
                and not pending_start
            ):
                await self.close_all_tcp_clients_gracefully()
            if self.ws_client is websocket:
                # Do not clear a newer WebSocket session that may have
                # connected while this one was shutting down.
                self.ws_client = None
                self.stale_request_ids.update(self.active_requests.keys())
            logger.info("WS client connection cleaned up")

    async def run(self) -> None:
        """Start the TCP and WebSocket servers and run until cancelled."""
        import websockets

        config = self.config
        update_runtime_status(
            enabled=True,
            starting=True,
            running=False,
            error=None,
            host=config.host,
            tcp_port=config.tcp_port,
            ws_port=config.ws_port,
            remote_agent_enabled=config.remote_agent_enabled,
            remote_agent_port=config.remote_agent_port,
            remote_agent_running=False,
        )
        logger.info("=" * 60)
        logger.info("  激光打标通信桥接程序")
        logger.info(f"  运行平台: {sys.platform}")
        logger.info(f"  TCP端口: {config.tcp_port}")
        logger.info(f"  WS端口: {config.ws_port}")
        logger.info(f"  本机内网IP: {self.get_local_service_ip()}")
        logger.info(f"  WS断开时是否关闭TCP连接: {'是' if config.close_tcp_when_ws_down else '否'}")
        logger.info(f"  请求ID过期时间: {config.request_expire_seconds}秒")
        logger.info(f"  print_end后F1最小等待: {config.f1_start_cooldown_seconds}秒")
        logger.info(f"  目标窗口: {config.win_title}")
        logger.info(f"  远程热键代理: {'启用' if config.remote_agent_enabled else '禁用'}")
        logger.info("=" * 60)

        asyncio.create_task(self.clean_expired_requests())

        async with AsyncExitStack() as stack:
            if config.remote_agent_enabled:
                try:
                    remote_server = await create_remote_agent_server(config)
                except Exception as e:
                    logger.error(
                        f"Failed to start remote hotkey agent on "
                        f"{config.remote_agent_host}:{config.remote_agent_port}: {e}"
                    )
                    remote_server = None
                if remote_server is not None:
                    await stack.enter_async_context(remote_server)
                    logger.info(
                        f"Remote hotkey agent started: tcp://{config.remote_agent_host}:{config.remote_agent_port}"
                    )
                    update_runtime_status(remote_agent_running=True)

            tcp_server = await asyncio.start_server(
                self.handle_tcp_client,
                config.host,
                config.tcp_port,
                reuse_port=sys.platform != "win32",
                reuse_address=True,
            )
            await stack.enter_async_context(tcp_server)
            logger.info(f"TCP service started: tcp://{config.host}:{config.tcp_port}")

            ws_server = await websockets.serve(
                self.handle_websocket,
                config.host,
                config.ws_port,
                reuse_port=sys.platform != "win32",
                reuse_address=True,
            )
            await stack.enter_async_context(ws_server)
            logger.info(f"WS service started: ws://{config.host}:{config.ws_port}")
            update_runtime_status(running=True, starting=False, error=None)

            logger.info("Background request cleanup task started")
            await asyncio.Future()

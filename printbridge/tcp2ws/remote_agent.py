"""Remote hotkey agent server migrated from the standalone remote_hotkey_agent.py.

Listens for ``TRIGGER_HOTKEY_ESC`` / ``TRIGGER_HOTKEY_F1`` commands and
simulates local ESC/F1 hotkeys on the configured marking software window.
"""

from __future__ import annotations

import asyncio
import logging

from .config import Tcp2WsConfig
from .windows import simulate_hotkey

logger = logging.getLogger("printbridge.tcp2ws")

TRIGGER_HOTKEY_ESC = "TRIGGER_HOTKEY_ESC"
TRIGGER_HOTKEY_F1 = "TRIGGER_HOTKEY_F1"
READ_TIMEOUT_SECONDS = 30


async def _handle_remote_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    config: Tcp2WsConfig,
) -> None:
    """Handle one remote trigger connection."""
    peer = writer.get_extra_info("peername")
    client_id = f"{peer[0]}:{peer[1]}" if peer else "unknown"

    try:
        data = await asyncio.wait_for(reader.read(1024), timeout=READ_TIMEOUT_SECONDS)
        command = data.decode("utf-8", errors="ignore").strip()

        if command == TRIGGER_HOTKEY_ESC:
            logger.info(f"Remote trigger received from {client_id}: execute ESC (finish job)")
            await asyncio.to_thread(simulate_hotkey, config.win_title, True, False)
            writer.write(b"SUCCESS")
            await writer.drain()

            # The original remote agent repeated ESC after replying to make
            # sure the marking software leaves the current job.
            for _ in range(3):
                await asyncio.sleep(1)
                await asyncio.to_thread(simulate_hotkey, config.win_title, True, False)
        elif command == TRIGGER_HOTKEY_F1:
            logger.info(f"Remote trigger received from {client_id}: execute F1 (start job)")
            await asyncio.to_thread(simulate_hotkey, config.win_title, False, True)
            writer.write(b"SUCCESS")
            await writer.drain()
        else:
            logger.warning(f"Remote trigger from {client_id} is invalid: {command!r}")
            writer.write(b"INVALID_COMMAND")
            await writer.drain()
    except asyncio.TimeoutError:
        logger.warning(f"Remote trigger connection timed out: {client_id}")
    except Exception as e:
        logger.error(f"Remote hotkey agent failed for {client_id}: {e}")
        try:
            writer.write(b"FAILED")
            await writer.drain()
        except Exception:
            pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def create_remote_agent_server(config: Tcp2WsConfig):
    """Start the remote hotkey agent TCP server and return the asyncio server."""
    return await asyncio.start_server(
        lambda reader, writer: _handle_remote_client(reader, writer, config),
        config.remote_agent_host,
        config.remote_agent_port,
        reuse_address=True,
    )

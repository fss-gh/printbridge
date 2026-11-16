"""CLI entry point for the TCP-to-WebSocket bridge.

Run with:

    python -m printbridge.tcp2ws
"""

from __future__ import annotations

import asyncio
import logging
import time

from ..config import PrintBridgeConfig
from ..logging_setup import setup_tcp2ws_logging
from .bridge import Tcp2WsBridge
from .config import Tcp2WsConfig

logger = logging.getLogger("printbridge.tcp2ws")


def run_with_auto_restart(config: Tcp2WsConfig | None = None) -> None:
    """Run the bridge, restarting automatically after unexpected errors."""
    restart_delay = 5
    restart_count = 0

    if config is None:
        main_config = PrintBridgeConfig.load()
        config = Tcp2WsConfig.from_dict(main_config.tcp2ws)
        setup_tcp2ws_logging(main_config.log_path)

    while True:
        try:
            asyncio.run(Tcp2WsBridge(config).run())
        except KeyboardInterrupt:
            logger.info("Service stopped by user")
            break
        except Exception as e:
            restart_count += 1
            logger.error(f"Service error: {e}")
            logger.info(f"Restarting in {restart_delay} seconds (restart #{restart_count})")
            time.sleep(restart_delay)
        else:
            break


def main() -> None:
    """Configure logging and run the bridge with auto-restart."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_with_auto_restart()


if __name__ == "__main__":
    main()

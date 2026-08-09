"""Auto-start registration for macOS (LaunchAgent) and Windows (registry)."""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("printbridge")


def install_autostart() -> None:
    """Auto-register PrintBridge to start on system boot.

    Called on every launch — safe to run multiple times.
    """
    import platform

    system = platform.system()

    try:
        if system == "Darwin":
            _install_macos()
        elif system == "Windows":
            _install_windows()
        else:
            logger.info(f"Auto-start not implemented for {system}")
    except Exception as e:
        logger.warning(f"Could not install auto-start: {e}")


def _install_macos() -> None:
    """Install macOS LaunchAgent."""
    if getattr(sys, "frozen", False):
        exe_path = os.path.realpath(sys.executable)
    else:
        exe_path = os.path.realpath(sys.argv[0])
        exe_path = f"/usr/bin/python3 {exe_path}"

    plist_name = "com.printbridge.agent.plist"
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / plist_name

    if not plist_path.exists():
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.printbridge.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>"""
        plist_path.write_text(plist_content)
        logger.info(f"Auto-start installed: {plist_path}")
    else:
        logger.info("Auto-start already configured")


def _install_windows() -> None:
    """Install Windows registry auto-start entry."""
    import winreg

    if getattr(sys, "frozen", False):
        exe_path = os.path.realpath(sys.executable)
    else:
        exe_path = f'pythonw.exe "{os.path.realpath(sys.argv[0])}"'

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    winreg.SetValueEx(key, "PrintBridge", 0, winreg.REG_SZ, exe_path)
    winreg.CloseKey(key)
    logger.info("Auto-start installed (Windows registry)")

"""Windows window activation and hotkey helpers for the TCP-to-WebSocket bridge."""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from ctypes import wintypes

logger = logging.getLogger("printbridge.tcp2ws")

_IS_WINDOWS = sys.platform.startswith("win")

if _IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    VK_ESCAPE = 0x1B
    VK_F1 = 0x70
    SW_RESTORE = 9
    SW_SHOW = 5

    kernel32.GetCurrentThreadId.argtypes = ()
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    user32.GetForegroundWindow.argtypes = ()
    user32.GetForegroundWindow.restype = wintypes.HWND

    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL

    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.IsIconic.restype = wintypes.BOOL

    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.ShowWindow.restype = wintypes.BOOL

    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL

    user32.SetFocus.argtypes = (wintypes.HWND,)
    user32.SetFocus.restype = wintypes.HWND

    user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.SendMessageW.restype = ctypes.c_ssize_t

    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int

    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int

    user32.EnumWindows.argtypes = (
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
        wintypes.LPARAM,
    )
    user32.EnumWindows.restype = wintypes.BOOL

    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.AttachThreadInput.restype = wintypes.BOOL
else:
    user32 = None
    kernel32 = None


def find_windows_by_title(title: str) -> list[int]:
    """Return visible window handles whose title exactly matches `title`."""
    if user32 is None:
        logger.warning("Window activation is only supported on Windows")
        return []

    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_proc(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            if buffer.value == title and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
        return True

    user32.EnumWindows(_enum_proc, 0)
    return found


def get_target_hwnd(title: str) -> int | None:
    """Get the first visible target window handle matching `title`."""
    windows = find_windows_by_title(title)
    if not windows:
        logger.error(f"Target window {title!r} not found")
        return None

    for hwnd in windows:
        if hwnd and user32.IsWindowVisible(hwnd):
            logger.info(f"Acquired window handle {hwnd} for {title!r}")
            return hwnd

    logger.error(f"Target window {title!r} exists but is hidden")
    return None


def send_key_to_hwnd(hwnd: int, vk_key: int) -> bool:
    """Send a key press directly to a window handle via WM_KEYDOWN/WM_KEYUP."""
    if user32 is None:
        return False
    try:
        user32.SendMessageW(hwnd, WM_KEYDOWN, vk_key, 0)
        time.sleep(0.05)
        user32.SendMessageW(hwnd, WM_KEYUP, vk_key, 0)
        return True
    except Exception:
        return False


def force_activate_target(title: str) -> bool:
    """Bring the target window to the foreground and give it focus."""
    if user32 is None:
        logger.warning("Window activation is only supported on Windows")
        return False

    hwnd = get_target_hwnd(title)
    if not hwnd:
        return False

    try:
        current_foreground = user32.GetForegroundWindow()
        if current_foreground != hwnd:
            user32.keybd_event(0, 0, 0, 0)
            time.sleep(0.1)
            user32.keybd_event(0, 0, 2, 0)

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.3)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)
            time.sleep(0.15)

        activated = False
        for retry in range(3):
            if user32.SetForegroundWindow(hwnd):
                activated = True
                break
            time.sleep(0.1 * (retry + 1))

        if not activated:
            logger.warning(f"Failed to bring {title!r} to the foreground after retries")
            return False

        user32.SetFocus(hwnd)
        time.sleep(0.1)
        user32.SetFocus(hwnd)
        user32.AttachThreadInput(
            user32.GetWindowThreadProcessId(hwnd, None),
            kernel32.GetCurrentThreadId(),
            True,
        )
        time.sleep(0.1)

        if user32.GetForegroundWindow() == hwnd:
            logger.info(f"{title!r} window activated successfully")
            return True

        logger.warning(f"{title!r} window was not actually brought to the foreground")
        return False
    except Exception as e:
        logger.error(f"Failed to activate {title!r}: {e}")
        return False


def simulate_hotkey(title: str, exec_esc: bool = False, exec_f1: bool = False) -> None:
    """Simulate ESC/F1 hotkeys on the target window."""
    hwnd = get_target_hwnd(title)
    if not hwnd:
        logger.error(f"Failed to get window handle for {title!r}, hotkey not sent")
        return

    force_activate_target(title)
    time.sleep(0.1)

    try:
        if exec_esc:
            if send_key_to_hwnd(hwnd, VK_ESCAPE):
                logger.info("Sent ESC key (finish job)")
            else:
                logger.error("Failed to send ESC key")
            if exec_f1:
                time.sleep(1)

        if exec_f1:
            if send_key_to_hwnd(hwnd, VK_F1):
                logger.info("Sent F1 key (start job)")
            else:
                logger.error("Failed to send F1 key")
    except Exception as e:
        logger.error(f"Hotkey simulation failed: {e}")

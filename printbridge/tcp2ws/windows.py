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
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    MAPVK_VK_TO_VSC = 0

    # SendInput structures (needed for real keyboard input to the foreground app).
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            ("mi", MOUSEINPUT),
            ("hi", HARDWAREINPUT),
        ]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("u", _INPUT_UNION),
        ]

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT),
        ]

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

    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.BringWindowToTop.restype = wintypes.BOOL

    user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.SendMessageW.restype = ctypes.c_ssize_t

    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.PostMessageW.restype = wintypes.BOOL

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

    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT

    user32.GetGUIThreadInfo.argtypes = (wintypes.DWORD, ctypes.POINTER(GUITHREADINFO))
    user32.GetGUIThreadInfo.restype = wintypes.BOOL

    user32.keybd_event.argtypes = (
        wintypes.BYTE,
        wintypes.BYTE,
        wintypes.DWORD,
        ctypes.c_size_t,
    )
    user32.keybd_event.restype = None
else:
    user32 = None
    kernel32 = None


def _window_title(hwnd: int) -> str:
    """Return the title of one top-level window."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def find_windows_by_title(title: str) -> list[int]:
    """Return visible top-level window handles matching `title`.

    Exact title matches are preferred; if there is no exact match, a
    case-insensitive substring match is used so titles like
    ``激光打标软件 - [项目]`` still work.
    """
    if user32 is None:
        logger.warning("Window activation is only supported on Windows")
        return []

    visible_windows: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_proc(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            window_title = _window_title(hwnd)
            if window_title:
                visible_windows.append((hwnd, window_title))
        return True

    user32.EnumWindows(_enum_proc, 0)

    exact = [hwnd for hwnd, window_title in visible_windows if window_title == title]
    if exact:
        return exact

    needle = title.casefold()
    return [
        hwnd
        for hwnd, window_title in visible_windows
        if needle in window_title.casefold()
    ]


def get_target_hwnd(title: str) -> int | None:
    """Get the first visible target window handle matching `title`."""
    windows = find_windows_by_title(title)
    if not windows:
        logger.error(f"Target window {title!r} not found")
        return None

    for hwnd in windows:
        if hwnd and user32.IsWindowVisible(hwnd):
            logger.info(f"Acquired window handle {hwnd} for {title!r}: {_window_title(hwnd)!r}")
            return hwnd

    logger.error(f"Target window {title!r} exists but is hidden")
    return None


def _window_thread_id(hwnd: int) -> int:
    """Return the GUI thread id that owns `hwnd`."""
    thread_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(thread_id))
    return thread_id.value


def get_focus_hwnd(hwnd: int) -> int:
    """Return the focused child/control of the target window when available."""
    thread_id = _window_thread_id(hwnd)
    if not thread_id:
        return hwnd

    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        return info.hwndFocus or info.hwndActive or hwnd
    return hwnd


def send_input_key(vk_key: int) -> bool:
    """Send a real keyboard key with SendInput to the current foreground window."""
    if user32 is None:
        return False

    inputs = (INPUT * 2)()
    for index, flags in ((0, 0), (1, KEYEVENTF_KEYUP)):
        inputs[index].type = INPUT_KEYBOARD
        inputs[index].ki.wVk = vk_key
        inputs[index].ki.wScan = 0
        inputs[index].ki.dwFlags = flags
        inputs[index].ki.time = 0
        inputs[index].ki.dwExtraInfo = 0

    sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    if sent != 2:
        error = ctypes.get_last_error()
        logger.warning(
            f"SendInput sent {sent}/2 events for VK 0x{vk_key:02X} "
            f"(GetLastError={error}); the target may be running elevated"
        )
        return False
    return True


def send_key_to_hwnd(hwnd: int, vk_key: int) -> bool:
    """Send a key press directly to a window handle via posted key messages."""
    if user32 is None:
        return False

    try:
        scan_code = user32.MapVirtualKeyW(vk_key, MAPVK_VK_TO_VSC)
        key_down_lparam = 1 | (scan_code << 16)
        key_up_lparam = (
            1
            | (scan_code << 16)
            | (1 << 30)
            | (1 << 31)
        )
        down_ok = user32.PostMessageW(hwnd, WM_KEYDOWN, vk_key, key_down_lparam)
        time.sleep(0.05)
        up_ok = user32.PostMessageW(hwnd, WM_KEYUP, vk_key, key_up_lparam)
        return bool(down_ok and up_ok)
    except Exception as e:
        logger.warning(f"Failed to post key 0x{vk_key:02X} to window {hwnd}: {e}")
        return False


def force_activate_target(title: str, hwnd: int | None = None) -> bool:
    """Bring the target window to the foreground and give it focus."""
    if user32 is None:
        logger.warning("Window activation is only supported on Windows")
        return False

    if not hwnd:
        hwnd = get_target_hwnd(title)
    if not hwnd:
        return False

    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.3)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)
            time.sleep(0.15)

        current_foreground = user32.GetForegroundWindow()
        if current_foreground != hwnd:
            # The foreground lock can reject SetForegroundWindow. A dummy
            # key event and AttachThreadInput are the standard workarounds.
            user32.keybd_event(0, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(0, 0, 2, 0)

            current_thread_id = kernel32.GetCurrentThreadId()
            foreground_thread_id = _window_thread_id(current_foreground) if current_foreground else 0
            target_thread_id = _window_thread_id(hwnd)
            attached_foreground = False
            attached_target = False
            try:
                if foreground_thread_id and foreground_thread_id != current_thread_id:
                    attached_foreground = bool(
                        user32.AttachThreadInput(current_thread_id, foreground_thread_id, True)
                    )
                if target_thread_id and target_thread_id != current_thread_id:
                    attached_target = bool(
                        user32.AttachThreadInput(current_thread_id, target_thread_id, True)
                    )
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetFocus(hwnd)
            finally:
                if attached_target:
                    user32.AttachThreadInput(current_thread_id, target_thread_id, False)
                if attached_foreground:
                    user32.AttachThreadInput(current_thread_id, foreground_thread_id, False)

            time.sleep(0.15)

        if user32.GetForegroundWindow() == hwnd:
            logger.info(f"{title!r} window activated successfully")
            return True

        logger.warning(f"{title!r} window is not the foreground window; will use direct key messages")
        return False
    except Exception as e:
        logger.error(f"Failed to activate {title!r}: {e}")
        return False


def _send_hotkey(hwnd: int, vk_key: int, label: str) -> bool:
    """Send one hotkey using SendInput when foreground, with message fallback."""
    # SendInput is the most compatible path because it produces real keyboard
    # input for the focused control. It only works when the target is
    # foreground; otherwise fall back to posting messages to the focused child.
    if user32.GetForegroundWindow() == hwnd:
        if send_input_key(vk_key):
            logger.info(f"Sent {label} key via SendInput")
            return True

    focus_hwnd = get_focus_hwnd(hwnd)
    targets: list[int] = []
    for target in (focus_hwnd, hwnd):
        if target and target not in targets:
            targets.append(target)

    for target in targets:
        if send_key_to_hwnd(target, vk_key):
            logger.info(f"Sent {label} key via PostMessage to window {target}")
            return True

    logger.error(f"Failed to send {label} key to window {hwnd}")
    return False


def simulate_hotkey(title: str, exec_esc: bool = False, exec_f1: bool = False) -> None:
    """Simulate ESC/F1 hotkeys on the target window."""
    hwnd = get_target_hwnd(title)
    if not hwnd:
        logger.error(f"Failed to get window handle for {title!r}, hotkey not sent")
        return

    force_activate_target(title, hwnd)
    time.sleep(0.15)

    try:
        if exec_esc:
            _send_hotkey(hwnd, VK_ESCAPE, "ESC (finish job)")
            if exec_f1:
                time.sleep(1)

        if exec_f1:
            _send_hotkey(hwnd, VK_F1, "F1 (start job)")
    except Exception as e:
        logger.error(f"Hotkey simulation failed: {e}")

"""Небольшие Windows-специфичные помощники.

На других платформах функции работают как безопасные no-op: приложение не
должно падать из-за отсутствия ``winreg`` или ``dwmapi``.
"""

from __future__ import annotations

import ctypes
import platform
import sys
from contextlib import suppress

try:
    import winreg
except ImportError:  # pragma: no cover - только не-Windows
    winreg = None


def get_windows_version() -> tuple[int, int, int]:
    try:
        parts = platform.version().split(".")
        return (
            int(parts[0]),
            int(parts[1]) if len(parts) > 1 else 0,
            int(parts[2]) if len(parts) > 2 else 0,
        )
    except (TypeError, ValueError, IndexError):
        return 10, 0, 0


def is_windows_theme() -> bool:
    """Возвращает True для тёмной темы Windows, False для светлой."""

    if sys.platform != "win32" or winreg is None:
        return True

    key = None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except OSError:
        return True
    finally:
        if key is not None:
            with suppress(OSError):
                winreg.CloseKey(key)


def _dwm_set(hwnd: int, attribute: int, value: int) -> bool:
    if sys.platform != "win32" or not hasattr(ctypes, "windll"):
        return False
    try:
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            attribute,
            ctypes.byref(ctypes.c_int(value)),
            ctypes.sizeof(ctypes.c_int),
        )
        return result == 0
    except (AttributeError, OSError, ValueError):
        return False


def set_title_bar_color(window, color_hex: str) -> bool:
    """Красит заголовок окна в Windows 11 (build 22000+)."""

    if sys.platform != "win32":
        return False

    major, _minor, build = get_windows_version()
    if major < 10 or build < 22000:
        return False

    try:
        hwnd = int(window.winId())
        red = int(color_hex[1:3], 16)
        green = int(color_hex[3:5], 16)
        blue = int(color_hex[5:7], 16)
        color_value = (blue << 16) | (green << 8) | red
        return _dwm_set(hwnd, 35, color_value)  # DWMWA_CAPTION_COLOR
    except (ValueError, TypeError, AttributeError):
        return False


def set_title_bar_light_theme(window, is_light: bool = True) -> bool:
    """Устанавливает светлую/тёмную тему заголовка."""

    if sys.platform != "win32":
        return False
    try:
        hwnd = int(window.winId())
        return _dwm_set(hwnd, 20, 0 if is_light else 1)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    except (ValueError, TypeError, AttributeError):
        return False

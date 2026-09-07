import ctypes
import sys
import platform
import winreg


def get_windows_version():
    try:
        parts = platform.version().split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        build = int(parts[2]) if len(parts) > 2 else 0
        return major, minor, build
    except:
        return 10, 0, 0

def is_windows_theme():
    """Проверяет какая тема в Windows."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0  # 0 = тёмная, 1 = светлая
    except:
        return True

def set_title_bar_color(window, color_hex):
    if sys.platform != "win32":
        return False

    major, minor, build = get_windows_version()

    # Цвет заголовка поддерживается только в Windows 11 (build 22000+)
    build = int(platform.version().split(".")[2]) if len(platform.version().split(".")) > 2 else 0

    if major < 10 or (major == 10 and build < 22000):
        return False

    try:
        hwnd = int(window.winId())

        r = int(color_hex[1:3], 16)
        g = int(color_hex[3:5], 16)
        b = int(color_hex[5:7], 16)
        color_value = (b << 16) | (g << 8) | r

        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            35,  # DWMWA_CAPTION_COLOR
            ctypes.byref(ctypes.c_int(color_value)),
            ctypes.sizeof(ctypes.c_int)
        )

        return result == 0
    except:
        return False


def set_title_bar_light_theme(window, is_light=True):
    """Устанавливает светлую/тёмную тему заголовка."""
    if sys.platform != "win32":
        return False

    try:
        hwnd = int(window.winId())
        value = ctypes.c_int(0 if is_light else 1)

        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            20,  # DWMWA_USE_IMMERSIVE_DARK_MODE
            ctypes.byref(value),
            ctypes.sizeof(value)
        )

        return result == 0
    except:
        return False
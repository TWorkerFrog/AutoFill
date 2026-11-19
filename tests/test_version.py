"""Версия приложения: ровно две цифры, третьей быть не должно."""

from core.version import APP_NAME, __version__


def test_version_is_two_part():
    assert __version__ == "1.1"
    # Третья цифра запрещена решением проекта: только «1.1», не «1.1.0».
    assert __version__.count(".") == 1


def test_version_is_numeric_parts():
    major, minor = __version__.split(".")
    assert major.isdigit()
    assert minor.isdigit()


def test_app_name():
    assert APP_NAME == "AutoFill"

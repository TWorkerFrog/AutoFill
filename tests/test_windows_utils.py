"""Windows-помощники: версия, тема системы, покраска заголовка окна."""

from __future__ import annotations

import sys

import pytest

from core import windows_utils as wu


class TestGetWindowsVersion:
    def test_returns_three_ints(self):
        major, minor, build = wu.get_windows_version()
        assert isinstance(major, int)
        assert isinstance(minor, int)
        assert isinstance(build, int)

    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("10.0.26200", (10, 0, 26200)),
            ("7", (7, 0, 0)),
            ("10.0", (10, 0, 0)),
            ("краказябра", (10, 0, 0)),
            ("", (10, 0, 0)),
        ],
    )
    def test_parse_variants(self, monkeypatch, version, expected):
        monkeypatch.setattr(wu.platform, "version", lambda: version)
        assert wu.get_windows_version() == expected


class TestIsWindowsTheme:
    def test_returns_bool(self):
        assert isinstance(wu.is_windows_theme(), bool)

    def test_non_windows_platform_reports_dark(self, monkeypatch):
        monkeypatch.setattr(wu.sys, "platform", "linux")
        assert wu.is_windows_theme() is True


class TestTitleBar:
    """На offscreen-платформе hwnd фиктивный: функция обязана вернуть
    bool и не упасть, какое бы значение ни вернула система."""

    @pytest.fixture
    def widget(self, qapp):
        from PySide6.QtWidgets import QWidget

        window = QWidget()
        window.winId()  # создаём нативный хэндл
        yield window
        window.deleteLater()

    def test_set_title_bar_color_returns_bool(self, widget):
        assert isinstance(wu.set_title_bar_color(widget, "#171717"), bool)

    def test_set_title_bar_light_theme_returns_bool(self, widget):
        assert isinstance(wu.set_title_bar_light_theme(widget, True), bool)

    def test_invalid_color_is_swallowed(self, widget):
        if sys.platform != "win32":
            pytest.skip("Проверка разбора hex только на Windows")
        assert wu.set_title_bar_color(widget, "#zzzzzz") is False

    def test_short_color_is_swallowed(self, widget):
        assert wu.set_title_bar_color(widget, "#fff") in (True, False)

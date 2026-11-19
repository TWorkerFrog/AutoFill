"""Расположение окон на экранах: несколько мониторов, узкие экраны, центрирование.

Экран подменяется через ``screen_of`` в namespace ``core.screen_utils``:
``place_window_on_screen`` резолвит его из своих глобальных переменных.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QWidget

import core.screen_utils as su
from core.screen_utils import center_window, place_window_on_screen


class FakeScreen:
    def __init__(self, x: int, y: int, width: int, height: int):
        self._geometry = QRect(x, y, width, height)

    def availableGeometry(self) -> QRect:  # noqa: N802 - имя из Qt API
        return self._geometry


@pytest.fixture
def widget(qapp):
    window = QWidget()
    window.resize(800, 600)
    yield window
    window.deleteLater()


def _use_screen(monkeypatch, screen: FakeScreen):
    monkeypatch.setattr(su, "screen_of", lambda _widget: screen)


class TestCenterWindow:
    def test_centers_on_screen_origin(self, widget, monkeypatch):
        _use_screen(monkeypatch, FakeScreen(0, 0, 1920, 1080))
        center_window(widget)
        assert widget.x() == (1920 - 800) // 2
        assert widget.y() == (1080 - 600) // 2

    def test_centers_on_second_monitor_with_offset(self, widget, monkeypatch):
        # Регрессия «окно уехало на другой монитор»: экран начинается
        # не в (0, 0), координаты берутся от topLeft экрана.
        _use_screen(monkeypatch, FakeScreen(1920, 0, 1366, 768))
        center_window(widget)
        assert widget.x() == 1920 + (1366 - 800) // 2
        assert widget.y() == (768 - 600) // 2

    def test_window_larger_than_screen_is_pinned_to_edge(self, widget, monkeypatch):
        widget.resize(4000, 2000)
        _use_screen(monkeypatch, FakeScreen(0, 0, 1920, 1080))
        center_window(widget)
        assert widget.x() == 0
        assert widget.y() == 0


class TestPlaceWindowOnScreen:
    def test_default_ratio_on_big_screen(self, widget, monkeypatch):
        _use_screen(monkeypatch, FakeScreen(0, 0, 2560, 1440))
        place_window_on_screen(widget)
        assert widget.width() == int(2560 * 0.78)
        assert widget.height() == int(1440 * 0.82)
        assert widget.x() == (2560 - widget.width()) // 2

    def test_minimum_sizes_on_small_screen(self, widget, monkeypatch):
        _use_screen(monkeypatch, FakeScreen(0, 0, 1000, 700))
        place_window_on_screen(widget)
        assert widget.width() == 900
        assert widget.height() == 600
        assert widget.x() == (1000 - 900) // 2

    def test_window_never_exceeds_screen(self, widget, monkeypatch):
        widget.resize(4000, 3000)
        _use_screen(monkeypatch, FakeScreen(0, 0, 1024, 768))
        place_window_on_screen(widget)
        assert widget.width() <= 1024
        assert widget.height() <= 768

    def test_uses_anchor_screen_not_window_screen(self, widget, monkeypatch):
        # Якорь (родительское окно) живёт на втором мониторе - новое окно
        # обязано открыться рядом с ним, а не на основном.
        anchor = QWidget()
        anchor.resize(100, 100)
        second = FakeScreen(1920, 0, 1366, 768)
        primary = FakeScreen(0, 0, 1920, 1080)
        try:
            monkeypatch.setattr(
                su, "screen_of", lambda target: second if target is anchor else primary
            )
            place_window_on_screen(widget, anchor)
            assert widget.x() >= 1920
            assert widget.width() == min(max(900, int(1366 * 0.78)), 1366)
        finally:
            anchor.deleteLater()

    def test_custom_ratios_and_minimums(self, widget, monkeypatch):
        _use_screen(monkeypatch, FakeScreen(0, 0, 2560, 1440))
        place_window_on_screen(widget, width_ratio=0.5, height_ratio=0.5, min_width=400, min_height=300)
        assert widget.width() == 1280
        assert widget.height() == 720

    def test_point_returned_inside_screen(self, widget, monkeypatch):
        _use_screen(monkeypatch, FakeScreen(1920, 111, 1366, 768))
        place_window_on_screen(widget)
        geometry = su.screen_of(widget).availableGeometry()
        assert geometry.contains(QPoint(widget.x(), widget.y()))
